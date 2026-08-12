import logging
import xml.dom.minidom
import shutil
from pathlib import Path
from typing import Optional, Union

import jinja2

from extractor import __version__
from extractor.pipeline.base import BasePipelineComponent

logger = logging.getLogger(__name__)


class TEISerializer(BasePipelineComponent):
    CUSTOM_DESCRIPTION = {"description": "Write out TEI files. "}

    def __init__(
        self, output_dir: Optional[Union[str, Path]] = None, copy_images: bool = False
    ):
        """
        Writes out an extracted EPub as a TEI-file.
        """
        # TODO find elegant way to handle none default values in CLI arg parsing
        if isinstance(output_dir, str):
            output_dir = None if output_dir.lower() == "none" else output_dir
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = None
        self.copy_images = copy_images
        if copy_images and output_dir is None:
            logger.warning(
                "Copy images won't have any effect since no new output_dir is"
                " specified."
            )

        # Setup Jinja rendering environment
        loader = jinja2.PackageLoader(
            "extractor.pipeline.serialization.tei",
            package_path="templates",
        )
        self.environment = jinja2.Environment(
            loader=loader, autoescape=True
        )

    def _prepare_data(self, extracted: dict) -> str:
        """Converts the dictionary representation of an
        extracted EPub to a TEI-document

        Args:
            extracted (dict): extracted Epub

        Returns:
            str: TEI content
        """
        extracted = extracted.copy()
        # Split into metadata and content
        content = extracted.pop("content")
        metadata = extracted
        # Prepare data
        metadata = self._prepare_metadata(metadata)

        # Prepare content
        content, image_data = self._prepare_content(content)
        # Allow to store images beside the TEI
        ...
        # Render
        return metadata, content, image_data

    def _prepare_metadata(self, metadata: dict) -> dict:
        """Parses the extracted metadata
        and returns a dictionary with entries ready to be
        inserted into the TEI-template.

        Args:
            metadata (dict): Raw extracted metdata

        Returns:
            dict: Template- and TEO-compliant metadata
        """
        prepared_metadata = {"extractor_version": __version__}
        prepared_metadata["title"] = metadata["title"]

        # Handle metadata from the EPub itself
        epub_metadata = metadata["epub_metadata"]

        # Date
        prepared_metadata["date"] = epub_metadata.get("date", "")

        # Author
        prepared_metadata["author"] = self._parse_creator(epub_metadata)

        # ISBN
        identifier, identifier_type = self._parse_identifier(epub_metadata)
        prepared_metadata["identifier"] = identifier
        prepared_metadata["identifier_type"] = identifier_type

        # Convert processing logs
        prepared_metadata["language_code"] = epub_metadata["language"]
        # TODOs:
        # Convert processing log timestamp to iso-compliant timestamp
        return prepared_metadata

    def _prepare_content(
        self, content: list[dict]
    ) -> tuple[list[dict], Optional[list[dict]]]:
        """Parses the content of an extracted EPub
        and returns a rendering compliant version.

        Args:
            content (list[dict]): Raw content

        Returns:
            list[dict]: Template- and TEO-compliant content
        """
        prepared_content, image_data = [], []
        if not self.copy_images:
            image_data = None
        # return prepared_content, image_data
        return content, image_data

    def _render_template(self, metadata: dict, content: list[str]) -> str:
        template = self.environment.get_template("tei_template.xml.jinja")
        rendering_kwargs = metadata
        rendering_kwargs["content"] = content
        tei_document = template.render(**rendering_kwargs)
        return tei_document

    def process(self, extracted: dict, file_path: Path) -> dict:
        metadata, content, image_data = self._prepare_data(extracted)
        tei_document = self._render_template(metadata, content)
        if self.output_dir is not None:
            # Setup new dir
            new_output_dir = self.output_dir / file_path.parent.stem
            new_output_dir.mkdir(exist_ok=True, parents=True)
            # If desired copy images
            if self.copy_images:
                orig_img_dir = file_path.parent / "imgs"
                assert (
                    orig_img_dir.is_dir() and orig_img_dir.exists()
                ), f"{orig_img_dir} does not exist"
                new_img_dir = new_output_dir / "imgs"
                shutil.copytree(str(orig_img_dir), str(new_img_dir), dirs_exist_ok=True)
            # Overwrite file_path
            file_path = new_output_dir / f"{file_path.stem}.xml"

        file_path.write_text(tei_document)
        return extracted

    @staticmethod
    def _parse_creator(epub_metadata: dict) -> str:
        creator_data = epub_metadata.get("creator", None)
        if creator_data is None:
            return ""
        elif isinstance(creator_data, str):
            name = creator_data
        else:
            name, _ = creator_data
        if name.count(",") and "von" in name.lower():
            # Catch names like von xxx, Marianne
            return [name]
        elif len(name.split(",")) == 2 and not all(
            [" " in n.strip() for n in name.split(",")]
        ):
            # Catch names like Cotton, Jerry
            return [name]

        else:
            return [n.strip() for n in name.split(",")]

    @staticmethod
    def _parse_identifier(epub_metadata: dict) -> str:
        identifier_data = epub_metadata.get("identifier", None)
        if identifier_data is None:
            return "", ""
        else:
            identifier, type_dict = identifier_data
            if "{http://www.idpf.org/2007/opf}scheme" in type_dict:
                identifier_type = type_dict["{http://www.idpf.org/2007/opf}scheme"]
            else:
                identifier_type = ""
            return identifier, identifier_type

