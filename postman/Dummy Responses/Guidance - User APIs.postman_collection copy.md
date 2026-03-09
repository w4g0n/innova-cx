# User APIs 

## Collection Metadata
- **info**: Collection identification + schema details (name, description, ids, link)

## Requests List
- **item**: Array of endpoints (each entry = one request)

---

## Endpoint: User Dashboard
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **User Dashboard - 200 OK**: Example success response (HTTP 200)

---

## Endpoint: My Open Complaints
- **request**: Request definition (method, headers, URL + query params)
- **response**: Saved example responses for this request
  - **Open Complaints List - 200 OK (search="")**: Example success response returning a list (HTTP 200)
  - **Open Complaints List - 200 OK (search="refund")**: Example success response returning an empty list (HTTP 200)

---

## Endpoint: Complaint Details
- **request**: Request definition (method, headers, URL with ticketId in path)
- **response**: Saved example responses for this request
  - **Ticket Details - 200 OK (CX-1122)**: Example success response (HTTP 200)
  - **Invalid Ticket - 404 Not Found (CX-0000)**: Example not-found response (HTTP 404)

---

## Endpoint: Report Issue
- **request**: Request definition (method, headers, URL with ticketId + action, body)
- **response**: Saved example responses for this request
  - **Issue Reported - 201 Created**: Example created/success response (HTTP 201)
  - **Missing Text - 400 Bad Request**: Example validation error response (HTTP 400)

---

## Endpoint: Submit Text Complaint
- **request**: Request definition (method, headers, URL, body)
- **response**: Saved example responses for this request
  - **Complaint Submitted - 201 Created**: Example created/success response (HTTP 201)
  - **Validation Error - 400 Bad Request**: Example validation error response (HTTP 400)

---

## Endpoint: Submit Audio Complaint
- **request**: Request definition (method, headers, URL, body)
- **response**: Saved example responses for this request
  - **Audio Complaint Submitted - 201**: Example created/success response (HTTP 201)
  - **Unsupported Media Type - 415**: Example unsupported media type response (HTTP 415)
  - **Payload Too Large - 413**: Example payload too large response (HTTP 413)

---

## Endpoint: Chat Options
- **request**: Request definition (method, headers, URL)
- **response**: Saved example responses for this request
  - **Quick Options - 200**: Example success response (HTTP 200)

---

## Endpoint: Send Chat Message
- **request**: Request definition (method, headers, URL, body)
- **response**: Saved example responses for this request
  - **Bot asks for location - 200**: Example conversational response (HTTP 200)
  - **Bot creates complaint draft - 200**: Example conversational response (HTTP 200)
  - **Too Many Requests - 429**: Example rate-limit error response (HTTP 429)

---

## Collection Scripts
- **event**: Collection-level scripts
  - **prerequest**: Pre-request script block (empty here)
  - **test**: Test script block (empty here)

---

## Collection Variables
- **variable**: Collection variables used in request URLs
  - **base_url**: Base URL value used in `{{base_url}}`
