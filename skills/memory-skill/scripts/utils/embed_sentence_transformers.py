import argparse
import base64
import json
import logging
import sys
from pathlib import Path

logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--text-b64", default="")
    parser.add_argument("--texts-file", default="")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(args.model)

    if args.texts_file:
        texts = json.loads(Path(args.texts_file).read_text(encoding="utf-8"))
        if not texts:
            print("[]")
            return
        vecs = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=args.batch_size,
        )
        print(json.dumps([vec.tolist() for vec in vecs], ensure_ascii=False))
        return

    if args.text_b64:
        text = base64.b64decode(args.text_b64).decode("utf-8").strip()
    else:
        text = sys.stdin.read().strip()

    if not text:
        print("[]")
        return

    vec = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
    print(json.dumps(vec.tolist(), ensure_ascii=False))


if __name__ == "__main__":
    main()
