import importlib
from typing import List

from .base import Pipeline


def build_pipeline(pipeline_components: List[str]) -> Pipeline:
    pipeline_module = importlib.import_module("extractor.pipeline")
    components = []
    for pipeline_component in pipeline_components:
        comp = getattr(pipeline_module, pipeline_component)
        components.append(comp())
    pipeline = Pipeline(components=components)
    return pipeline
