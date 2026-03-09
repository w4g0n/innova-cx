# Operator API

## Collection Metadata
- **info**: Collection identification and schema details (name, description, ids, schema version, collection link)

---

## Requests List
- **item**: Array of endpoints contained in this collection

---

## Endpoint: Operator System Dashboard
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **System Dashboard - 200 OK**: Example success response (HTTP 200)
  - **Dashboard - 503 Service Unavailable**: Example service unavailable response (HTTP 503)

---

## Endpoint: Model Performance Analytics
- **request**: Request definition (method, headers, URL + query params)
- **response**: Saved example responses for this request
  - **Model Performance Analytics – 200 OK**: Example success response (HTTP 200)
  - **Invalid Filters - 400 Bad Request**: Example bad request response (HTTP 400)

---

## Endpoint: Review Cases (optional split)
- **request**: Request definition (method, headers, URL + query params)
- **response**: Saved example responses for this request
  - **Review Cases - 200 OK**: Example success response (HTTP 200)
  - **Missing Token - 401 Unauthorized**: Example unauthorized response (HTTP 401)

---

## Endpoint: Chatbot Performance Analytics
- **request**: Request definition (method, headers, URL + query params)
- **response**: Saved example responses for this request
  - **Chatbot Performance Analytics - 200 OK**: Example success response (HTTP 200)
  - **Analytics - 500 Internal Server Error**: Example server error response (HTTP 500)

---

## Endpoint: Handled Complaints
- **request**: Request definition (method, headers, URL + query params)
- **response**: Saved example responses for this request
  - **Handled Complaints (All) - 200 OK**: Example success response (HTTP 200)
  - **Invalid Filter - 400 Bad Request**: Example bad request response (HTTP 400)
  - **Handled Complaints (Resolved only) - 200 OK**: Example success response (HTTP 200)
  - **Handled Complaints (Unresolved only) - 200 OK**: Example success response (HTTP 200)
  - **Handled Complaints (Partially resolved) - 200 OK**: Example success response (HTTP 200)

---

## Collection Scripts
- **event**: Collection-level scripts
  - **prerequest**: Pre-request script block (empty)
  - **test**: Test script block (empty)

---

## Collection Variables
- **variable**: Collection variables used in request URLs
  - **base_url**: Base URL value used in `{{base_url}}`
