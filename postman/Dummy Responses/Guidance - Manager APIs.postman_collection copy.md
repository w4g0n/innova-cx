# Manager APIs

## Collection Metadata
- **info**: Collection identification and schema details (name, description, ids, schema version, collection link)

---

## Requests List
- **item**: Array of endpoints contained in this collection

---

## Endpoint: Manager Dashboard page
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **New Request – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: View All Complaints page
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **View All Complaints page – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Assign / Reassign complaint
- **request**: Request definition (method, headers, body, URL with ticketId)
- **response**: Saved example responses for this request
  - **Assign / Reassign complaint – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get approval requests
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get approval requests – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Approve request
- **request**: Request definition (method, headers, URL with requestId)
- **response**: Saved example responses for this request
  - **Approve request – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Reject request
- **request**: Request definition (method, headers, URL with requestId)
- **response**: Saved example responses for this request
  - **Reject request – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get employees list
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get employees list – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get employee report
- **request**: Request definition (method, headers, URL with employeeId)
- **response**: Saved example responses for this request
  - **Get employee report – 200 OK**: Example success response (HTTP 200)

---

## Endpoint: Get trends data
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Get trends data – 200 OK**: Example success response (HTTP 200)

---

## Collection Scripts
- **event**: Collection-level scripts
  - **prerequest**: Pre-request script block (empty)
  - **test**: Test script block (empty)

---

## Collection Variables
- **variable**: Collection variables used in request URLs
  - **base_url**: Base URL value used in `{{base_url}}`
