from IPython.display import HTML, display

""" Some utility functions to render the extracted JSON files inside Jupyter Notebooks """


def display_recursively(extracted, numbering=False):
    """Recurses throught the JSON-structure of an extracted epub,
    and displays the texts rendered as HTML (in Jupyter-Notebooks)

    Args:
        extracted (Dict): Extracted epub
    """
    i = [1]

    def display_texts(extracted):
        for name, field in extracted.items():
            if name == "text" and (content := extracted[name]) is not None:
                if isinstance(content, list):
                    content = "***".join(content)
                if numbering:
                    print(i[0])
                    print("_" * 60)
                display(HTML(content))
                i[0] = i[0] + 1
            if isinstance(field, dict):
                display_texts(field)
            if isinstance(field, list):
                for entry in field:
                    if isinstance(entry, dict):
                        display_texts(entry)

    display_texts(extracted)


def xmlify(extracted, numbering=False):
    """Recurses through the JSON-structure of an extracted epub,
    and displays the texts rendered as HTML (in Jupyter-Notebooks)

    Args:
        extracted (Dict): Extracted epub
    """
    contents = []

    def to_xml(extracted):
        for name, field in extracted.items():
            if name == "text" and (content := extracted[name]) is not None:
                if isinstance(content, list):
                    content = "***".join(content)
                contents.append(content)
            if isinstance(field, dict):
                to_xml(field)
            if isinstance(field, list):
                for entry in field:
                    if isinstance(entry, dict):
                        to_xml(entry)

    to_xml(extracted)
    doc = (
        '<root xmlns="http://www.tei-c.org/ns/1.0"'
        ' xmlns:html="http://www.w3.org/1999/xhtml">{content}</root>'
    )
    return doc.format(content="\n".join(contents))
