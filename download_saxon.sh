#!/bin/bash

zip_url="https://github.com/Saxonica/Saxon-HE/releases/download/SaxonHE12-3/saxon-resources-12.zip"
mkdir -p saxon
wget -O saxon-resources-12.zip "$zip_url"
unzip -q saxon-resources-12.zip -d saxon
rm saxon-resources-12.zip
echo "Download and extraction completed. The contents are saved in the 'saxon' directory."
