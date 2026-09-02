"""ONNX-Runtime embedding path for BAAI/bge-small-en-v1.5.

Replaces the torch + sentence-transformers stack on both the query side (rag.py)
and the one-off chunk-embedding side (load_embeddings.py).

Why: `import sentence_transformers` pulls in torch unconditionally, so even its
`backend="onnx"` mode keeps ~200 MB of torch resident. That is what OOM'd the
Render free tier (512 MB). This module imports only onnxruntime + tokenizers +
numpy — no torch anywhere in the path.

Model specifics (from the model's own 1_Pooling/config.json + sentence_bert_config.json):
  - pooling  = CLS token (first position), then L2-normalize
  - max_seq_length = 512, lower-cased (handled inside tokenizer.json's normalizer)
  - embedding dim = 384

The "Represent this sentence for searching relevant passages: " instruction is
prepended to QUERIES ONLY (rag.QUERY_INSTRUCTION); callers do that, same as the
old path. Chunk/passage text is embedded verbatim.

The ONNX graph and tokenizer are pulled from the BAAI repo itself (BAAI ships
`onnx/model.onnx`), cached by huggingface_hub like the old torch weights were.
"""

from __future__ import annotations

import functools

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

MODEL_REPO = "BAAI/bge-small-en-v1.5"
ONNX_FILE = "onnx/model.onnx"
MAX_SEQ_LEN = 512
EMBED_DIM = 384


@functools.lru_cache(maxsize=1)
def _session() -> ort.InferenceSession:
    path = hf_hub_download(MODEL_REPO, ONNX_FILE)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1  # free-tier CPU is small; don't oversubscribe
    return ort.InferenceSession(path, sess_options=opts, providers=["CPUExecutionProvider"])


@functools.lru_cache(maxsize=1)
def _tokenizer() -> Tokenizer:
    tok = Tokenizer.from_file(hf_hub_download(MODEL_REPO, "tokenizer.json"))
    tok.enable_truncation(max_length=MAX_SEQ_LEN)
    tok.enable_padding(pad_id=0, pad_token="[PAD]")
    return tok


def warm() -> None:
    """Load the ONNX session + tokenizer now (call from FastAPI startup)."""
    _session()
    _tokenizer()


def encode(texts: str | list[str], batch_size: int = 32) -> np.ndarray:
    """Embed text -> float32, L2-normalized.

    str  -> shape (384,)
    list -> shape (len, 384)
    """
    single = isinstance(texts, str)
    items = [texts] if single else list(texts)
    if not items:
        return np.empty((0, EMBED_DIM), dtype=np.float32)

    tok, sess = _tokenizer(), _session()
    out = np.empty((len(items), EMBED_DIM), dtype=np.float32)

    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        encs = tok.encode_batch(batch)
        feed = {
            "input_ids": np.array([e.ids for e in encs], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encs], dtype=np.int64),
            "token_type_ids": np.array([e.type_ids for e in encs], dtype=np.int64),
        }
        (last_hidden,) = sess.run(["last_hidden_state"], feed)
        cls = last_hidden[:, 0].astype(np.float32)  # CLS pooling
        cls /= np.linalg.norm(cls, axis=1, keepdims=True) + 1e-12  # L2 normalize
        out[start : start + len(batch)] = cls

    return out[0] if single else out
