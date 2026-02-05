from core.controller import handle_inquiry, handle_complaint

print("Chatbot ready.")
print("Modes: inquiry | complaint")
print("Type 'exit' to quit.\n")

# ---- session state ----
mode = input("Select mode (inquiry / complaint): ").strip().lower()
state = {"attempts": 0}

while True:
    user_input = input("You: ")

    if user_input.lower() in ["exit", "quit"]:
        print("Exiting.")
        break

    if mode == "inquiry":
        response = handle_inquiry(user_input, state)

    elif mode == "complaint":
        response = handle_complaint(user_input, state)

    else:
        response = "Invalid mode selected."

    print("Bot:", response)
