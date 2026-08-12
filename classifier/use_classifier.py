import json
import argparse
import os
import glob
import joblib
import chardet
import re

def remove_xml_tags(text):
    """Removes XML/HTML tags from text."""
    return re.sub(r'<.*?>', '', text)

def add_is_narrative_to_json(input_json_path, output_json_path, model):
    """
    Adds 'is_narrative' classification to each JSON object containing a 'text' field.

    Args:
        input_json_path (str): Path to the input JSON file.
        output_json_path (str): Path to save the updated JSON file.
        model: Trained classification model.
    """
    with open(input_json_path, 'rb') as raw_file:
        raw_data = raw_file.read()
        detected_encoding = chardet.detect(raw_data)['encoding']
    
    with open(input_json_path, 'r', encoding=detected_encoding) as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            print(f"File {input_json_path} is not valid JSON or is empty.")
            return

    def process_json(obj):
        """Recursively processes the JSON to add 'is_narrative' predictions."""
        if isinstance(obj, dict):
            if 'text' in obj:
                clean_text = remove_xml_tags(obj['text'])
                obj['is_narrative'] = bool(model.predict([clean_text])[0])
            for key, value in obj.items():
                process_json(value)
        elif isinstance(obj, list):
            for item in obj:
                process_json(item)

    process_json(data)

    with open(output_json_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)

def main():
    parser = argparse.ArgumentParser(description="Use a trained classifier to add 'is_narrative' to JSON files.")
    parser.add_argument("input_folder", help="Path to the folder containing JSON files to process.")
    parser.add_argument("model_path", help="Path to the trained classifier model.")
    parser.add_argument("output_folder", help="Path to the folder where processed JSON files will be saved.")
    args = parser.parse_args()

    input_folder = args.input_folder
    model_path = args.model_path
    output_folder = args.output_folder

    model = joblib.load(args.model_path)

    os.makedirs(output_folder, exist_ok=True)

    json_files = glob.glob(os.path.join(input_folder, '*.json'))

    if not json_files:
        print(f"No JSON files found in {input_folder}.")
        return

    for input_file in json_files:
        try:
            file_name = os.path.basename(input_file)

            output_file = os.path.join(output_folder, file_name)

            print(f"Processing {input_file}...")
            add_is_narrative_to_json(input_file, output_file, model)
            print(f"Saved processed file to {output_file}")
        except Exception as e:
            print(f"Error processing file {input_file}: {e}")

if __name__ == "__main__":
    main()
