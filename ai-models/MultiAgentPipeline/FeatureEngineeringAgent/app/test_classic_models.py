import joblib
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_MODEL_PATH = "models/"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_models(target_name):
    target_path = BASE_MODEL_PATH + target_name + "/"

    models = {
        "Logistic": joblib.load(target_path + "logistic.pkl"),
        "SVM": joblib.load(target_path + "svm.pkl"),
        "RandomForest": joblib.load(target_path + "rf.pkl"),
    }

    label_encoder = joblib.load(target_path + "label_encoder.pkl")

    return models, label_encoder


def main():

    embedder = SentenceTransformer(EMBED_MODEL_NAME)

    business_models, business_le = load_models("business_impact")
    safety_models, safety_le = load_models("safety_concern")

    test_cases = [

        """hi, i'm calling regarding an unresolved issue.
we are facing poor ventilation in one of our meeting rooms.
our unit is located in tech block.
this was reported earlier but hasn't been resolved.
it is uncomfortable but operations are still running normally.
please do.""",

        """hi, i'm calling regarding an unresolved issue.
we are facing intermittent internet connectivity in the office.
our unit is located in zone b – sme offices.
this was reported earlier but hasn't been resolved.
our staff are experiencing workflow interruptions throughout the day.
please do.""",

        """hi, i'm calling regarding an unresolved issue.
we are facing elevator malfunction in our building.
our unit is located in corporate offices zone a.
this was reported earlier but hasn't been resolved.
employees were briefly stuck inside and are concerned about safety.
please escalate this urgently.""",

        """hi, i'm calling regarding an unresolved issue.
we are facing flickering lights in the warehouse area.
our unit is located in logistics cluster south.
this was reported earlier but hasn't been resolved.
it is affecting productivity and visibility during operations.
please do.""",

        """hi, i'm calling regarding an unresolved issue.
we are facing visible structural cracks forming along the warehouse wall.
our unit is located in logistics cluster north.
this was reported earlier but hasn't been resolved.
staff are worried about potential collapse and safety risks.
please escalate immediately.""",

        """hi, i'm calling regarding an unresolved issue.
we are facing repeated false fire alarm activations.
our unit is located in retail plaza central.
this was reported earlier but hasn't been resolved.
the constant alarms are causing panic among customers and staff.
please escalate urgently.""",

        """hi, i'm calling regarding an unresolved issue.
we are facing water stagnation in the basement parking area.
our unit is located in community retail strip.
this was reported earlier but hasn't been resolved.
there is risk of slipping hazards and electrical exposure.
please escalate immediately.""",

        """hi, i'm calling regarding an unresolved issue.
we are facing printer malfunction at the reception desk.
our unit is located in tech block.
this was reported earlier but hasn't been resolved.
this is slowing down paperwork processing slightly.
please do.""",

        """hi, i'm calling regarding an unresolved issue.
we are facing an unauthorized access attempt near our storage area.
our unit is located in logistics cluster south.
this was reported earlier but hasn't been resolved.
employees feel unsafe and sensitive materials are at risk.
please escalate immediately."""
    ]

    for i, text in enumerate(test_cases):
        print("\n" + "=" * 60)
        print(f"TEST CASE {i+1}")
        print("=" * 60)

        embedding = embedder.encode([text], convert_to_numpy=True)

        print("\nBusiness Impact Predictions:")
        for name, model in business_models.items():
            pred = model.predict(embedding)
            label = business_le.inverse_transform(pred)[0]
            print(f"  {name}: {label}")

        print("\nSafety Concern Predictions:")
        for name, model in safety_models.items():
            pred = model.predict(embedding)
            label = safety_le.inverse_transform(pred)[0]
            print(f"  {name}: {label}")


if __name__ == "__main__":
    main()