# Employee APIs

## Collection Metadata
- **info**: Collection identification and schema details (name, description, ids, schema version, collection link)

---

## Requests List
- **item**: Array of endpoints contained in this collection

---

## Endpoint: Get Employee Dashboard Summary
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get Employee Dashboard Summary – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get My Open Tickets
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get My Open Tickets – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get Available Monthly Reports
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get Available Monthly Reports – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get Monthly Performance Report
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get Monthly Performance Report – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get All Assigned Complaints
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get All Assigned Complaints – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get Complaint Details
- **request**: Request definition (method, headers, URL with ticketId)
- **response**: Saved example responses for this request
  - **Get Complaint Details – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Rescore Ticket
- **request**: Request definition (method, headers, URL with id)
- **response**: Saved example responses for this request
  - **Rescore Ticket – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Reroute
- **request**: Request definition (method, headers, URL with id)
- **response**: Saved example responses for this request
  - **Reroute – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Resolve
- **request**: Request definition (method, headers, URL with id)
- **response**: Saved example responses for this request
  - **Resolve – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get Tickets Overview
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get Tickets Overview – 200 OK**: Example success response (HTTP 200)

---

## Collection Authentication
- **auth**: Authentication configuration applied at the collection level (Bearer token used for employee access)

---

## Collection Scripts
- **event**: Collection-level scripts
  - **prerequest**: Pre-request script block (empty)
  - **test**: Test script block (empty)

---

## Collection Variables
- **variable**: Collection variables used in request URLs
  - **base_url**: Base URL value used in `{{base_url}}`