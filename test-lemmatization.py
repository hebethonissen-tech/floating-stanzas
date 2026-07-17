"""
GaLAHaD lemmatization caller (best-effort).
Tries to call the GaLAHaD tagger model 'hug-tdn-1400-1600' to lemmatize a string.

How to use:
- Set BASE_URL to the base API URL of GaLAHaD (example: https://portal.clarin.ivdnt.org/galahad/api)
- Set INPUT_TEXT to the text you want lemmatized.
- If the API requires auth, set AUTH_TOKEN (Bearer) or set USERNAME/PASSWORD and adapt auth code.
- If one endpoint fails, uncomment other attempted endpoints or update them to the exact path
  you see in the Swagger UI.

This client prints the response and returns a Python object (parsed JSON when possible).
"""

import requests
import json
from typing import Optional, Dict, Any

# ------------- CONFIGURE -------------
BASE_URL = "https://portal.clarin.ivdnt.org/galahad/api"  # replace if Swagger shows a different base
MODEL_NAME = "hug-tdn-1400-1600"
INPUT_TEXT = "Ic rede een mael in een bossche dal. Ic vant gescreven overal" 
AUTH_TOKEN: Optional[str] = None  # e.g. "eyJhbGciOi..."; otherwise None

# You may need these headers (adjust Content-Type according to Swagger: e.g. application/json, text/plain, application/folia+xml)
COMMON_HEADERS = {
    "Accept": "application/json",
}
if AUTH_TOKEN:
    COMMON_HEADERS["Authorization"] = f"Bearer {AUTH_TOKEN}"

# ------------- UTILS -------------
def try_post(url: str, headers: Dict[str,str], data=None, json_body=None, files=None, params=None, timeout=30) -> requests.Response:
    """
    Helper that issues a POST and returns Response. Caller handles exceptions.
    """
    return requests.post(url, headers=headers, data=data, json=json_body, files=files, params=params, timeout=timeout)

def pretty_print_resp(resp: requests.Response):
    print("STATUS:", resp.status_code)
    ct = resp.headers.get("Content-Type","")
    print("CONTENT-TYPE:", ct)
    if "application/json" in ct:
        try:
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        except Exception:
            print(resp.text[:1000])
    else:
        # fallback: print first 1000 chars
        print(resp.text[:1000])

# ------------- ATTEMPT COMMON ENDPOINTS -------------
def call_galahad_lemmatizer(text: str, model: str = MODEL_NAME) -> Dict[str,Any]:
    """
    Attempts several likely endpoints for running a tagger.
    Returns a dict with 'endpoint', 'status_code', 'response' (parsed JSON or raw text).
    """
    attempts = []

    # Candidate endpoints (most likely patterns). Replace/augment with the exact path from Swagger if you have it.
    candidates = [
        # pattern: POST /taggers/{tagger}/annotate  (common)
        f"{BASE_URL}/taggers/{model}/annotate",
        # pattern: POST /taggers/{tagger}/process
        f"{BASE_URL}/taggers/{model}/process",
        # pattern: POST /taggers/{tagger}  (tagger invoked via POST directly)
        f"{BASE_URL}/taggers/{model}",
        # pattern: POST /taggers/run?model={model}
        f"{BASE_URL}/taggers/run",
        # pattern: POST /annotate?model={model}
        f"{BASE_URL}/annotate",
    ]

    # Many tagger APIs accept JSON: {"text":"..."} — try that first.
    json_body = {"text": text}
    # Some APIs expect model as a query param
    params = {"model": model}

    for url in candidates:
        # Try JSON body + model param
        headers = COMMON_HEADERS.copy()
        headers["Content-Type"] = "application/json"
        try:
            print(f"\nTrying POST {url}  (JSON body + model param)")
            resp = try_post(url, headers=headers, json_body=json_body, params=params)
        except Exception as e:
            print("Request failed:", e)
            attempts.append({"endpoint": url, "error": str(e)})
            continue

        if resp.status_code in (200,201):
            # success — try to parse JSON
            try:
                parsed = resp.json()
            except Exception:
                parsed = {"raw_text": resp.text}
            return {"endpoint": url, "status_code": resp.status_code, "response": parsed}

        # if it returned 400/415 maybe the API expects plain text or a file upload
        print("Not 200 — status", resp.status_code)
        pretty_print_resp(resp)
        attempts.append({"endpoint": url, "status_code": resp.status_code, "text_preview": resp.text[:800]})

        # Next try: send plain text (text/plain)
        try:
            headers2 = COMMON_HEADERS.copy()
            headers2["Content-Type"] = "text/plain"
            print(f"\nTrying POST {url}  (plain text body, Content-Type: text/plain) ")
            resp2 = try_post(url, headers=headers2, data=text, params=params)
        except Exception as e:
            print("Request failed:", e)
            attempts.append({"endpoint": url + " (text/plain)", "error": str(e)})
            continue

        if resp2.status_code in (200,201):
            try:
                parsed2 = resp2.json()
            except Exception:
                parsed2 = {"raw_text": resp2.text}
            return {"endpoint": url + " (text/plain)", "status_code": resp2.status_code, "response": parsed2}
        print("Not 200 — status", resp2.status_code)
        pretty_print_resp(resp2)
        attempts.append({"endpoint": url + " (text/plain)", "status_code": resp2.status_code, "text_preview": resp2.text[:800]})

        # Next try: file upload with form-data field 'file' (many APIs accept file upload of FoLiA/NAF)
        try:
            headers3 = COMMON_HEADERS.copy()
            # don't set Content-Type; requests will set it for multipart/form-data
            files = {"file": ("input.txt", text, "text/plain")}
            print(f"\nTrying POST {url}  (multipart file upload 'file')")
            resp3 = try_post(url, headers=headers3, files=files, params=params)
        except Exception as e:
            print("Request failed:", e)
            attempts.append({"endpoint": url + " (multipart)", "error": str(e)})
            continue

        if resp3.status_code in (200,201):
            try:
                parsed3 = resp3.json()
            except Exception:
                parsed3 = {"raw_text": resp3.text}
            return {"endpoint": url + " (multipart)", "status_code": resp3.status_code, "response": parsed3}
        print("Not 200 — status", resp3.status_code)
        pretty_print_resp(resp3)
        attempts.append({"endpoint": url + " (multipart)", "status_code": resp3.status_code, "text_preview": resp3.text[:800]})

    # if we reach here: no attempt succeeded
    return {"endpoint": None, "status_code": None, "error": "All attempts failed", "attempts": attempts}

# ------------- RUN -------------
if __name__ == "__main__":
    result = call_galahad_lemmatizer(INPUT_TEXT, MODEL_NAME)
    print("\nFINAL RESULT:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
Explanation — step by step (what each part does and why)
Configuration block

BASE_URL: The root of the GaLAHaD API. Replace it with the exact base URL shown in the Swagger (sometimes Swagger shows /galahad/api/v1 or similar).

MODEL_NAME: hug-tdn-1400-1600 per your request — many APIs use the model name in the path (e.g. /taggers/{model}) or as a query parameter (e.g. ?model=hug-tdn-1400-1600). The code tries both approaches.

INPUT_TEXT: the text to lemmatize.

AUTH_TOKEN: if the API requires bearer tokens, put it here (the code will include it in the Authorization header).

Common headers

Accept: application/json to ask for JSON responses.

Authorization: Bearer <token> if AUTH_TOKEN is provided.

Candidate endpoints
Because the live Swagger was not reachable from my environment, I prepared a list of likely endpoint patterns (these cover the common naming conventions used in REST APIs generated by Swagger/Controller frameworks). The candidates are:

POST /taggers/{model}/annotate

POST /taggers/{model}/process

POST /taggers/{model}

POST /taggers/run

POST /annotate
Replace/add the exact endpoint name you find in your Swagger UI if it differs.

Try common request formats (JSON, plain text, multipart)
Tagger APIs vary in how they accept input:

JSON { "text": "..." } is common for small requests.

text/plain body is used by simpler endpoints.

multipart file upload is used when the API expects FoLiA/NAF files. The code tries all three for each endpoint candidate.

Model parameter
The code sends model as a query parameter ?model=hug-tdn-1400-1600 because some endpoints accept it there. If the Swagger shows a different method (e.g. inside the JSON body), put "model": "hug-tdn-1400-1600" in the JSON body instead.

Auth and CLARIN accounts

GaLAHaD web application often requires CLARIN authentication for the web UI. The API may require a token or cookie created via a CLARIN Single Sign-On flow. If that's the case you must either:

obtain a bearer API token and set AUTH_TOKEN, or

perform the login flow programmatically (e.g., OAuth2/SSO) to obtain cookies/tokens; the Swagger UI usually documents the auth mechanism.

The code allows you to set AUTH_TOKEN. If the API requires a different auth method (cookie/session), you will need to adapt the code to perform that specific flow and attach the requests.Session() cookies.

Response handling

On HTTP 200/201 the code tries to parse JSON and returns it. That JSON typically contains tokens with lemma fields or a structured FoLiA/NAF payload with lemma attributes. The code prints the response content type and a pretty JSON preview to help you inspect results.

How to interpret expected response

If successful, the API typically returns either:

a JSON structure listing tokens with POS and lemma fields, e.g. {"tokens":[{"text":"Dit","lemma":"dit","pos":"DET"}, ...]}, or

an XML FoLiA/NAF document in the response (Content-Type application/xml), which you then parse for <lemma> attributes.

Inspect the Content-Type header and the Swagger response schema to pick the right parser.

Quick example of parsing a simple JSON response
If the service returns JSON like:

json
Code kopiëren
{
  "tokens": [
    {"token": "Dit", "lemma": "dit"},
    {"token": "is", "lemma": "zijn"},
    {"token": "een", "lemma": "een"},
    {"token": "voorbeeldzin", "lemma": "voorbeeldzin"},
    {"token": "om", "lemma": "om"},
    {"token": "te", "lemma": "te"},
    {"token": "lemmatizeren", "lemma": "lemmatizeren"},
    { "token": ".", "lemma": "."}
  ]
}
You would extract lemmas like:

python
Code kopiëren
lemmas = [t.get("lemma") for t in resp_json.get("tokens", [])]
print("Lemmas:", lemmas)
# -> ["dit", "zijn", "een", "voorbeeldzin", "om", "te", "lemmatizeren", "."]
What I couldn't do (transparency)
I could not fetch the Swagger page from my environment (timeout), so I could not copy the exact endpoint path, parameter names, or request/response schema. The code above is therefore best-effort and intentionally flexible: it tries the most common endpoint names and input formats. If you open the Swagger UI on your side you will see the exact operation name and request/response schema — then you can either:

replace the candidates entry with the exact endpoint path, or

tell me the exact operationId or the request body schema from the Swagger UI and I will immediately produce an exact, minimal Python call that matches the API precisely.

Next steps for you (two quick options)
If you can open the Swagger UI now: copy the exact POST endpoint path for running a tagger (the operation that accepts text for annotation) and paste it here (just the path), and I will immediately produce the single exact requests.post(...) snippet you can run.

If you want to run the code now: download the script above, set BASE_URL to your GaLAHaD API base, set INPUT_TEXT, add AUTH_TOKEN if needed, run it — it will try likely endpoints and print detailed diagnostics so you can see what to adjust.

Would you like me to:

craft the single exact request after you paste the endpoint path/Swagger schema, or

try to fetch the Swagger again from my side now (I can try once more), or

prepare a short parser for FoLiA/NAF if the service returns XML?












