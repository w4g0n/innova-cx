import pandas as pd
from sklearn.model_selection import train_test_split
import os

CLEANED_PATH = "data/processed/cleaned.csv"
PROCESSED_PATH = "data/processed/"

def main():
    df = pd.read_csv(CLEANED_PATH)

    # 70% train, 30% temp
    train_df, temp_df = train_test_split(
        df,
        test_size=0.30,
        stratify=df["business_impact"],
        random_state=42
    )

    # 15% val, 15% test
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        stratify=temp_df["business_impact"],
        random_state=42
    )

    os.makedirs(PROCESSED_PATH, exist_ok=True)

    train_df.to_csv(PROCESSED_PATH + "train.csv", index=False)
    val_df.to_csv(PROCESSED_PATH + "val.csv", index=False)
    test_df.to_csv(PROCESSED_PATH + "test.csv", index=False)

    print("Split complete.")
    print("Train:", len(train_df))
    print("Validation:", len(val_df))
    print("Test:", len(test_df))

    print("\nTrain distribution:")
    print(train_df["business_impact"].value_counts())

    print("\nValidation distribution:")
    print(val_df["business_impact"].value_counts())

    print("\nTest distribution:")
    print(test_df["business_impact"].value_counts())


if __name__ == "__main__":
    main()