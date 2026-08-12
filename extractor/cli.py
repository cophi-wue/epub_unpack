import importlib
import inspect
import json
import logging
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import click
from click.core import Command, Context
from tqdm.auto import tqdm

from .extractor import EpubExtractor
from .image import Image, extract_images
from .json import EPubUnpackJSONEncoder, read_json, write_json
from .pipeline import Pipeline, build_pipeline

"""CLI-interface logic"""

# Setup logger


def build_logger(
    logging_handlers: Optional[List[logging.Handler]] = None,
) -> logging.Logger:
    if logging_handlers is None:
        logging_handlers = [logging.NullHandler()]
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=logging_handlers,
        level=logging.NOTSET,
    )
    return logger


def build_file_logger(log_path: str) -> logging.Logger:
    return build_logger([logging.FileHandler(filename=log_path, mode="a+")])


@click.group()
def cli():
    """
    \b
    ####### ######                          #     #
    #       #     # #    # #####     ######  #   #  ##### #####    ##    ####  #####  ####  #####
    #       #     # #    # #    #    #        # #     #   #    #  #  #  #    #   #   #    # #    #
    #####   ######  #    # #####     #####     #      #   #    # #    # #        #   #    # #    #
    #       #       #    # #    #    #        # #     #   #####  ###### #        #   #    # #####
    #       #       #    # #    #    #       #   #    #   #   #  #    # #    #   #   #    # #   #
    ####### #        ####  #####     ###### #     #   #   #    # #    #  ####    #    ####  #    #

    Convert EPubs into TEI.

    For more information visit: https://github.com/LennartKeller/epub_unpack
    """
    ...


@cli.command()
@click.argument("epub_dir", type=click.Path(exists=True, path_type=Path))
@click.argument("output_dir", type=click.Path(exists=False, path_type=Path))
@click.option(
    "-l",
    "--log-path",
    default=None,
    type=click.Path(exists=False, dir_okay=False, writable=True),
    help="Path to write out logs.",
)
@click.option("-c", "--check", is_flag=True, help="Enable sanity checks.")
@click.option("-s", "--strict", is_flag=True, help="Disable merciful loading of EPubs.")
@click.option("-v", "--verbose", is_flag=True)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable debug mode and start pu.db at exception.",
)
@click.option(
    "-i",
    "--ignore-images",
    is_flag=True,
    help="Do not write out images from the EBook.",
)
def extract(
    epub_dir, output_dir, log_path, check, strict, verbose, debug, ignore_images
):
    """
    Extract EPubs into JSON containing texts as TEI


    EPUB_DIR: Directory to recursively search of *.epub files

    OUTPUT_DIR: Directory to write out the JSON files
    """

    if log_path is not None:
        logger = build_file_logger(log_path=log_path)
    else:
        logger = build_logger()

    # Search for epubs
    # epub_dir = Path(epub_dir)
    epub_files = list(sorted(epub_dir.glob("**/*.epub")))

    # DEBUG CERTAIN FILES
    # target_files = set([f for f in epub_files if "unger" in f.stem.lower() and "texas-mar" in f.stem.lower()])
    # print(target_files)
    # epub_files = [f for f in epub_files if f in target_files]

    click.echo(
        f"Found {len(epub_files)} EPUBS in {epub_dir.absolute()} and all its"
        " subdirectories."
    )

    # Setup output dir
    # output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    # Init extractor
    extractor = EpubExtractor(
        verbose=verbose,
        merciful=not strict,
        do_sanity_check=check,
        debug=debug,
        include_images=not ignore_images,
    )

    # Unpack
    click.echo("Start extraction...")

    # Setup pbar and lists for failed/ success
    # TODO DEBUG
    # epub_files = [f for f in epub_files if "folge 0718" in f.name.lower()]

    pbar = tqdm(epub_files[:])
    extracted_epubs = []
    failed_epubs = []
    for file in pbar:
        pbar.set_description(f"Extracting: {file.name}")
        logger.info(f"Extractor called on {file}")
        try:
            # Ignore ebooklib's deprecation warnings for nxc_files
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                extracted = extractor(file)
            logger.info(f"Success on {file}")
            extracted_epubs.append(str(file.absolute()))
        except Exception as e:
            logger.critical(f"Failed to extract {file}")
            logger.exception(e)
            failed_epubs.append((str(file.absolute()), str(e)))
            if debug:
                try:
                    import pudb

                    pu.db
                except ModuleNotFoundError:
                    logger.warning("Debug mode is enabled but pudb is not installed.")
            continue
        # Setup output dir for novel
        file_name = file.stem + ".json"
        file_dir = output_dir / file.stem
        file_dir.mkdir(exist_ok=True, parents=True)
        # Remove images from extracted and write them to separate dir
        if not ignore_images:
            image_dir = file_dir / "imgs"
            extract_images(extracted, image_dir=image_dir)
        # Write out file content
        file_path = file_dir / file_name
        write_json(extracted, file_path)
    click.echo("Finished extraction!")

    # Create final report
    final_report_path = output_dir / "EXTRACTION_REPORT.json"
    final_report = {
        "params": {
            "epub_dir": str(epub_dir.absolute()),
            "output_dir": str(output_dir.absolute()),
            "log_path": log_path if log_path is None else str(log_path),
            "strict": strict,
            "verbose": verbose,
        },
        "finished": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        "success": extracted_epubs,
        "failed": failed_epubs,
    }
    with final_report_path.open("w") as f:
        json.dump(final_report, f, indent=4)

    # Print final msg
    click.echo(
        f"Successfully extracted {len(extracted_epubs)} EPUBS | Failed to extract"
        f" {len(failed_epubs)} EPUBS."
    )
    click.echo(f"Wrote extraction-report to {final_report_path}")


@cli.command()
@click.argument(
    "input_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.argument(
    "output_dir",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--model-path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to the trained classifier model.",
)
@click.option(
    "-l",
    "--log-path",
    default=None,
    type=click.Path(exists=False, dir_okay=False, writable=True),
    help="Path to write out logs.",
)
@click.option("--strict", is_flag=True, help="Stop on any extraction error.")
@click.option("--ignore-images", is_flag=True, help="Do not extract images.")
@click.option(
    "--skip-existing", is_flag=True, help="Skip books that already have output JSON."
)
@click.option(
    "--no-report", is_flag=True, help="Do not write the bulk_processing_report.json."
)
def bulk_process(
    input_path, output_dir, model_path, log_path, strict, ignore_images, skip_existing, no_report
):
    """
    Run the entire pipeline (Extract -> InferredType -> Classify) for EPUB(s).
    
    INPUT_PATH: Directory to search for *.epub files OR a single *.epub file.
    """
    if log_path is not None:
        log_path = Path(log_path)
        build_logger([logging.FileHandler(log_path, mode="w")])
    else:
        build_logger()

    if input_path.is_file():
        epub_files = [input_path]
    else:
        epub_files = list(input_path.glob("**/*.epub"))
    
    if not epub_files:
        click.echo(f"No EPUB files found in {input_path}")
        return

    click.echo(f"Found {len(epub_files)} EPUBS. Starting processing...")

    from .bulk_runner import BulkProcessor

    processor = BulkProcessor(
        output_dir=output_dir,
        model_path=model_path,
        strict=strict,
        include_images=not ignore_images,
        skip_existing=skip_existing,
    )

    results = []
    pbar = tqdm(epub_files)
    for epub_file in pbar:
        pbar.set_description(f"Processing: {epub_file.name}")
        status = processor.process_book(epub_file)
        results.append(status)

    # Summary
    success_count = sum(
        1
        for r in results
        if r["steps"]["serialization"] == "success"
    )
    click.echo(
        f"Processing finished. Successfully processed {success_count}/{len(epub_files)} books."
    )

    if not no_report:
        # Write detailed report
        report_path = Path(output_dir) / "bulk_processing_report.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_books": len(epub_files),
            "success_count": success_count,
            "results": results,
        }
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=4)
        click.echo(f"Detailed report written to {report_path}")


class PipelineComponentGroup(click.Group):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.components: Dict[str, click.Command] = self._lazy_load()

        if (external_src_file := os.environ.get("EPX_EXT_COMP")) is not None:
            external_src_file = Path(external_src_file).expanduser().absolute()
            assert external_src_file.exists()
            self._extend_with_external_components(external_src_file)

    def _extend_with_external_components(self, external_src_file: Path):
        module_name = external_src_file.stem
        external_components = self._lazy_load(
            module_name=module_name, file_path=external_src_file
        )
        self.components |= external_components

    def _lazy_load(
        self, module_name: Optional[str] = None, file_path: Optional[str] = None
    ):
        components = {}

        if module_name is None:
            pipeline_module = importlib.import_module("extractor.pipeline")
        else:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            pipeline_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = pipeline_module
            spec.loader.exec_module(pipeline_module)
            # pipeline_module = importlib.import_module(pipeline_module)

        all_components = [
            cls
            for cls in dir(pipeline_module)
            if cls[0].isupper() and not cls.startswith("Base") and not cls == "Pipeline"
        ]
        for component_name in all_components:
            component_cls = getattr(pipeline_module, component_name)

            # Register constructor args as options
            command_options = []
            constructor_signature = inspect.signature(component_cls.__init__)
            constructor_params = [
                p
                for p in constructor_signature.parameters.items()
                if p[0] not in ("self", "args", "kwargs")
            ]
            for name, constructor_param in constructor_params:
                option_kwargs = {
                    "param_decls": [f"--{name}"],
                    "show_default": True,
                }
                if (default_val := constructor_param.default) != inspect._empty:
                    if default_val is not None:
                        option_kwargs["default"] = default_val
                    else:
                        option_kwargs["default"] = "None"
                option = click.Option(**option_kwargs)
                command_options.append(option)

            def make_callback(component_cls):
                def callback(*args, **kwargs):
                    return component_cls(*args, **kwargs)

                return callback

            # Prepare docstring if available
            constructor_docstring = component_cls.__init__.__doc__
            if constructor_docstring and not constructor_docstring.strip().startswith(
                "Initialize self."
            ):
                constructor_docstring = "\n\n".join(
                    constructor_docstring.strip().split("\n")
                )
            else:
                # If not available try to use the description field
                try:
                    constructor_docstring = component_cls.CUSTOM_DESCRIPTION[
                        "description"
                    ]
                except KeyError:
                    constructor_docstring = None

            component_command = click.Command(
                name=component_name,
                params=command_options,
                callback=make_callback(component_cls=component_cls),
                help=constructor_docstring,
                short_help="",
            )
            components[component_command.name] = component_command

        return components

    def list_commands(self, ctx: Context) -> List[str]:
        return super().list_commands(ctx) + list(self.components.keys())

    def get_command(self, ctx: Context, cmd_name: str) -> Optional[Command]:
        if cmd_name in self.components:
            return self.components[cmd_name]
        return super().get_command(ctx, cmd_name)


@cli.group(chain=True, invoke_without_command=True, cls=PipelineComponentGroup)
@click.argument(
    "json_path_or_dir",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "-l",
    "--log-path",
    default=None,
    type=click.Path(exists=False, dir_okay=False, writable=True),
    help="Path to write out logs.",
)
def post_process(json_path_or_dir, log_path):
    """
    Apply post-processing operations to the extracted books
    """
    ...


@post_process.result_callback()
def post_process_pipeline(components, json_path_or_dir, log_path):
    if log_path is not None:
        logger = build_logger([logging.FileHandler(log_path, mode="w")])
    else:
        logger = build_logger()

    # Build Pipeline
    # pipeline = build_pipeline(pipeline_components=pipeline_components)
    pipeline = Pipeline(components=components)
    # Iterate over file(s) and apply pipeline
    # json_path_or_dir = Path(json_path_or_dir)
    if json_path_or_dir.is_dir():
        json_files = [
            f
            for f in json_path_or_dir.glob("**/*.json")
            if not f.name == "EXTRACTION_REPORT.json"
        ]
    else:
        json_files = [json_path_or_dir]
    pbar = tqdm(json_files)

    for json_file in pbar:
        pbar.set_description(json_file.name)
        logger.info(f"Applying post-processing to {json_file}")
        extracted = read_json(json_file)
        extracted = pipeline(extracted=extracted, file_path=json_file)

    click.echo("Finished")


if __name__ == "__main__":
    cli()
