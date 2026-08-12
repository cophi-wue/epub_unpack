import json
import glob
import re
import os
import argparse
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import cross_val_score, cross_validate, GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import classification_report
import joblib

def extract_fields(data):
    """Recursively extracts fields with 'text' and relevant keys from nested JSON."""
    extracted = []
    if isinstance(data, dict):
        if "text" in data:
            fields_to_extract = {
                key: data[key]
                for key in ["text", "inferred-type", "true-type", "is_narrative"]
                if key in data
            }
            if fields_to_extract:
                extracted.append(fields_to_extract)
        for key, value in data.items():
            extracted += extract_fields(value)
    elif isinstance(data, list):
        for item in data:
            extracted += extract_fields(item)
    return extracted

def remove_xml_tags(text):
    """Removes XML/HTML tags from text."""
    return re.sub(r'<.*?>', '', text)

def load_data(folder_path):
    """Loads and processes JSON files from the given folder path."""
    files = glob.glob(os.path.join(folder_path, "*/*"))
    results = []
    for file in files:
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                results.extend(extract_fields(data))
        except json.JSONDecodeError:
            print(f"Invalid JSON: {file}")
        except Exception as e:
            print(f"Error processing {file}: {e}")
    return results

def build_model(X, y):
    """Builds and tunes a logistic regression model using GridSearchCV."""
    model_pipeline = make_pipeline(TfidfVectorizer(), LogisticRegression())
    param_grid = {
        'logisticregression__C': [0.1, 1, 10],
        'logisticregression__solver': ['liblinear', 'lbfgs']
    }
    grid_search = GridSearchCV(model_pipeline, param_grid, cv=7, scoring='accuracy')
    grid_search.fit(X, y)
    return grid_search.best_estimator_, grid_search.best_score_

def main():
    parser = argparse.ArgumentParser(description="Train a classifier for narrative detection.")
    parser.add_argument('input_folder', type=str, help="Path to folder containing annotated JSON files.")
    parser.add_argument('output_model', type=str, help="Path to save the trained model.")
    args = parser.parse_args()

    print("Loading data...")
    results = load_data(args.input_folder)
    df = pd.DataFrame(results)
    df = df.dropna(subset=['is_narrative'])
    df['is_narrative'] = df['is_narrative'].astype(int)
    df['clean_text'] = df['text'].apply(remove_xml_tags)

    X = df['clean_text']
    y = df['is_narrative']

    print("Training model...")
    best_model, best_score = build_model(X, y)
    print(f"Best Model Accuracy: {best_score:.3f}")

    print("Validating using cross-validation...")
    cv_results = cross_validate(best_model, X, y, cv=7, scoring=['accuracy', 'precision', 'recall', 'f1'])

    print("\nDetailed Cross-Validation Metrics:")
    for metric in ['accuracy', 'precision', 'recall', 'f1']:
        print(f"{metric.capitalize()}: {cv_results['test_' + metric].mean():.3f}")

    print(f"Saving model to {args.output_model}...")
    joblib.dump(best_model, args.output_model)
    print("Model saved successfully.")

if __name__ == "__main__":
    main()
