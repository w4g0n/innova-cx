

## –
## –
## –
## –
## –
## –
## Early Model Architecture
User selects inquiry or complaint instead of classification
## Input:
Tex t   o r   Au d i o
If audio convert to text (transcriber)
And carry audio analysis signal weight
Early classification
Chatbot tries to resolve complaint/ inquiry
If it cant human intervention:
Chatbot processes complaints and tries to resolve
## Ticket Creation
Classification Model (Inquiry or Complaint)
Inquiry: added to system, routed to department, model/
chatbot suggest employee resolutions
## Complaints:
## Signal Extraction Layer
DSPY prioritization logic
Routed to departments
Suggest resolution from model
## Optional:
Employee gives model feedback
## Reroute (department)
## Rescore (priority)
Suggestion Feedback (for the suggest resolution)
## Model Development Plan
## 0 Definitions
Define inputs
## Tickets

And dspy input and output
Sync with backed and front end
2 Transcriber and Audio Analysis
Audio and text normalization
Audio Emotional signal
## 4 Chatbot
Attempts to assist
5 ticket creation
7 Text sentiment and Audio sentiment
8 Severity / importance model
9 DSPY prioritization
10 routing + suggestion model
Same llm as chatbot
11 feedback loop
Retrains 8 basically