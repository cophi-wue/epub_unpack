### Classifier

These two scripts are designed to automatically classify all text passages of any JSON dime novel file into *narrative* and *non-narrative.*

#### Make classifier
The `make_classifier.py` script takes anntotated JSON files as input (folder called **EpubAnnos**) and creates a classifier based on a weighted BoW model (`TfidfVectorizer`). The classifier as run by the script can be found in the `testing` folder, which has an F1 of 0.96.

Example usage (arguments are folder of the annotation files and classifier save file):

```bash
python make_classifier.py /mnt/data/users/hagen/epub_unpack/EpubAnnos/ testing/classifier
```

![epub1](https://github.com/user-attachments/assets/5f6b88a8-f196-4337-8093-9a5285a3822f)


#### Use classifier
The second script `use_classifier.py` takes a number of non-annotated JSON files an adds the *is-narrative* fields to any text segment using the previously created classifier. One example annotated file can be found in the `testing` folder.

Example usage (arguments are input folder, classifier, and output folder):

```bash
python use_classifier.py /mnt/data/users/hagen/epub_unpack/extracted-heftromane/Wolf_Mythor-Paket-2_9783845399478 testing/classifier testing/
```

![epub3](https://github.com/user-attachments/assets/4589fe6f-a430-47d4-8133-6f83cdaeb986)

**Future work:** 
* Consolidate with rule-based approach (*inferred type* in JSON, script see `extractor/pipeline/type_inference.py`)
* Another classifier for the annotated *true-type* fields (exact instead of binary classification)
* Merge these scripts into the full pipeline for an easier workflow (maybe?)
