from typing import ClassVar, Dict, Optional

from open_notebook.database.repository import repo_query
from open_notebook.domain.base import ObjectModel, RecordModel
from open_notebook.models import (
    MODEL_CLASS_MAP,
    EmbeddingModel,
    LanguageModel,
    ModelType,
    SpeechToTextModel,
    TextToSpeechModel,
)


class Model(ObjectModel):
    table_name: ClassVar[str] = "model"
    name: str
    provider: str
    type: str

    @classmethod
    def get_models_by_type(cls, model_type):
        models = repo_query(
            "SELECT * FROM model WHERE type=$model_type;", {"model_type": model_type}
        )
        return [Model(**model) for model in models]


class DefaultModels(RecordModel):
    record_id: ClassVar[str] = "open_notebook:default_models"

    default_chat_model: Optional[str] = None
    default_transformation_model: Optional[str] = None
    large_context_model: Optional[str] = None
    default_text_to_speech_model: Optional[str] = None
    default_speech_to_text_model: Optional[str] = None
    # default_vision_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    default_tools_model: Optional[str] = None


class ModelManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._model_cache: Dict[str, ModelType] = {}
            self._default_models = None
            self.refresh_defaults()

    def get_model(self, model_id: str, **kwargs) -> ModelType:
        cache_key = f"{model_id}:{str(kwargs)}"

        if cache_key in self._model_cache:
            cached_model = self._model_cache[cache_key]
            if not isinstance(
                cached_model,
                (LanguageModel, EmbeddingModel, SpeechToTextModel, TextToSpeechModel),
            ):
                raise TypeError(
                    f"Cached model is of unexpected type: {type(cached_model)}"
                )
            return cached_model

        assert model_id, "Model ID cannot be empty"
        model: Model = Model.get(model_id)

        if not model:
            raise ValueError(f"Model with ID {model_id} not found")

        if not model.type or model.type not in MODEL_CLASS_MAP:
            raise ValueError(f"Invalid model type: {model.type}")

        provider_map = MODEL_CLASS_MAP[model.type]
        if model.provider not in provider_map:
            raise ValueError(
                f"Provider {model.provider} not compatible with {model.type} models"
            )

        model_class = provider_map[model.provider]
        model_instance = model_class(model_name=model.name, **kwargs)

        # Special handling for language models that need langchain conversion
        if model.type == "language":
            model_instance = model_instance

        self._model_cache[cache_key] = model_instance
        return model_instance

    def refresh_defaults(self):
        """Refresh the default models from the database"""
        self._default_models = DefaultModels()

    @property
    def defaults(self) -> DefaultModels:
        """Get the default models configuration"""
        if not self._default_models:
            self.refresh_defaults()
            if not self._default_models:
                raise RuntimeError("Failed to initialize default models configuration")
        return self._default_models

    @property
    def speech_to_text(self, **kwargs) -> SpeechToTextModel:
        """Get the default speech-to-text model"""
        model = self.get_default_model("speech_to_text", **kwargs)
        if not isinstance(model, SpeechToTextModel):
            raise TypeError(f"Expected SpeechToTextModel but got {type(model)}")
        return model

    @property
    def text_to_speech(self, **kwargs) -> TextToSpeechModel:
        """Get the default text-to-speech model"""
        model = self.get_default_model("text_to_speech", **kwargs)
        if not isinstance(model, TextToSpeechModel):
            raise TypeError(f"Expected TextToSpeechModel but got {type(model)}")
        return model

    @property
    def embedding_model(self, **kwargs) -> EmbeddingModel:
        """Get the default embedding model"""
        model = self.get_default_model("embedding", **kwargs)
        if not isinstance(model, EmbeddingModel):
            raise TypeError(f"Expected EmbeddingModel but got {type(model)}")
        return model

    def get_default_model(self, model_type: str, **kwargs) -> ModelType:
        """
        Get the default model for a specific type.

        Args:
            model_type: The type of model to retrieve (e.g., 'chat', 'embedding', etc.)
            **kwargs: Additional arguments to pass to the model constructor
        """
        model_id = None

        if model_type == "chat":
            model_id = self.defaults.default_chat_model
        elif model_type == "transformation":
            model_id = (
                self.defaults.default_transformation_model
                or self.defaults.default_chat_model
            )
        elif model_type == "tools":
            model_id = (
                self.defaults.default_tools_model or self.defaults.default_chat_model
            )
        elif model_type == "embedding":
            model_id = self.defaults.default_embedding_model
        elif model_type == "text_to_speech":
            model_id = self.defaults.default_text_to_speech_model
        elif model_type == "speech_to_text":
            model_id = self.defaults.default_speech_to_text_model
        elif model_type == "large_context":
            model_id = self.defaults.large_context_model

        if not model_id:
            raise ValueError(f"No default model configured for type: {model_type}")

        return self.get_model(model_id, **kwargs)

    def clear_cache(self):
        """Clear the model cache"""
        self._model_cache.clear()


model_manager = ModelManager()
