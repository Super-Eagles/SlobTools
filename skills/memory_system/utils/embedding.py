from .. import config
import logging
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(config.EMBED_MODEL)
    return _model


def embed(text):
    vec = _get_model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts):
    vecs = _get_model().encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]
