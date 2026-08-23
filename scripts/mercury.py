#!/usr/bin/env python3
"""
Mercury Bank API client — READ ONLY.

Every call is a GET. This module contains no POST/PUT/PATCH/DELETE path at all,
so it cannot mutate the account even if a read-write token is supplied by mistake.

Traps encoded here (each one is a real thing in Mercury's own docs, cited):

  T1  /account/{id}/transactions defaults `start` to "30 days before the current
      date".  Omitting it returns a SHORT list that looks complete.  We never call
      that endpoint for the ledger; we use /transactions, and we always pass dates.

  T2  /transactions `start`/`end` filter on **createdAt**, not postedAt.  Mercury's
      own doc: "your Mercury transactions on your Dashboard might have their postedAt
      date displayed, as opposed to createdAt".  A financial-year cut must use
      postedAt, or a txn created 31-Mar and posted 02-Apr lands in the wrong year and
      the closing balance will not tie.  We pull on postedStart/postedEnd AND pull a
      createdAt superset so the difference is measurable rather than assumed.

  T3  limit maxes at 1000 and defaults to 1000.  A page that comes back exactly full
      is NOT proof there is no more.  We always follow the cursor until it is empty.

  T4  Auth is basic-auth (token as username, blank password) or
      `Authorization: Bearer secret-token:mercury_...`.  The literal `secret-token:`
      prefix is PART of the credential.  We normalise either form.
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.mercury.com/api/v1"
TOKEN_PATH = os.environ.get("MERCURY_TOKEN_FILE", "/root/.config/mercury/token.json")


class MercuryError(RuntimeError):
    pass


def load_token(explicit=None):
    """Token from arg, then $MERCURY_TOKEN, then the on-disk file. Never logged."""
    tok = explicit or os.environ.get("MERCURY_TOKEN")
    if not tok and os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as fh:
            tok = json.load(fh).get("token")
    if not tok:
        raise MercuryError(
            "No Mercury token. Put it in %s as {\"token\": \"secret-token:mercury_...\"} "
            "or export MERCURY_TOKEN." % TOKEN_PATH
        )
    tok = tok.strip()
    # T4: the credential includes the `secret-token:` prefix. Accept it with or without.
    if not tok.startswith("secret-token:"):
        tok = "secret-token:" + tok
    return tok


def redact(tok):
    """Safe to print. Never let a full token reach a log, a page, or a repo."""
    tail = tok[-4:] if len(tok) > 4 else "????"
    return "secret-token:mercury_…%s" % tail


class Mercury:
    def __init__(self, token=None, verbose=True):
        self.token = load_token(token)
        self.verbose = verbose
        self.calls = 0

    def _get(self, path, params=None, retries=4):
        url = BASE + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            # repeated keys for array params (status, accountId, cardId)
            pairs = []
            for k, v in clean.items():
                if isinstance(v, (list, tuple)):
                    pairs.extend((k, str(x)) for x in v)
                else:
                    pairs.append((k, str(v)))
            if pairs:
                url += "?" + urllib.parse.urlencode(pairs)
        last = None
        for attempt in range(retries):
            req = urllib.request.Request(url)
            # T4: basic auth, token as username, empty password.
            basic = base64.b64encode(("%s:" % self.token).encode()).decode()
            req.add_header("Authorization", "Basic " + basic)
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "gcalit-balance-sheet/1.0")
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self.calls += 1
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")[:400]
                if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    wait = 2 ** attempt
                    if self.verbose:
                        print("  HTTP %s on %s — retry in %ss" % (e.code, path, wait), file=sys.stderr)
                    time.sleep(wait)
                    last = MercuryError("HTTP %s %s :: %s" % (e.code, path, body))
                    continue
                # Never swallow the server's own error — it is the diagnosis.
                hint = ""
                if e.code == 401:
                    hint = ("  → token rejected. Check it is the FULL string including the "
                            "`secret-token:` prefix, and that it has not been auto-deleted "
                            "(Mercury deletes tokens unused for 45 days).")
                if e.code == 403:
                    hint = "  → token is valid but lacks the scope for this endpoint."
                raise MercuryError("HTTP %s %s :: %s%s" % (e.code, path, body, hint))
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    last = MercuryError("transport %s on %s" % (e, path))
                    continue
                raise MercuryError("transport failure on %s: %s" % (path, e))
        raise last

    # ---- simple reads -------------------------------------------------

    def organization(self):
        return self._get("/organization")

    def credit_accounts(self):
        return self._get("/credit").get("accounts", [])

    # ---- cursor-paginated reads ---------------------------------------

    def _cursor_pages(self, path, key, params=None, id_field="id"):
        """T3: follow the cursor until a page comes back empty. A full page is not an end."""
        out, seen, cursor, page_no = [], set(), None, 0
        while True:
            p = dict(params or {})
            p["limit"] = 1000
            if cursor:
                p["start_after"] = cursor
            data = self._get(path, p)
            items = data.get(key, []) if isinstance(data, dict) else data
            if not items:
                break
            page_no += 1
            fresh = 0
            for it in items:
                iid = it.get(id_field)
                if iid in seen:      # defensive: a mis-paged cursor must not loop forever
                    continue
                seen.add(iid)
                out.append(it)
                fresh += 1
            if self.verbose:
                print("    page %d: %d items (%d new, %d total)" % (page_no, len(items), fresh, len(out)))
            if fresh == 0:
                break
            cursor = items[-1].get(id_field)
            if not cursor:
                break
        return out

    def accounts(self):
        return self._cursor_pages("/accounts", "accounts")

    def cards(self):
        return self._cursor_pages("/cards", "cards")

    def statements(self, account_id, start=None, end=None):
        return self._cursor_pages(
            "/account/%s/statements" % account_id, "statements",
            {"start": start, "end": end, "order": "asc"},
        )

    def transactions(self, posted_start=None, posted_end=None,
                     created_start=None, created_end=None,
                     account_ids=None, status=None):
        """
        T2: pass posted_start/posted_end for a financial-year cut.
        Pass created_start/created_end only to measure the createdAt-vs-postedAt gap.
        """
        params = {
            "postedStart": posted_start, "postedEnd": posted_end,
            "start": created_start, "end": created_end,
            "accountId": account_ids, "status": status, "order": "asc",
        }
        return self._cursor_pages("/transactions", "transactions", params)
