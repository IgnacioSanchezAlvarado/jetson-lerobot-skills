"""Offline GR00T eval — feed dataset frames through the model.

Uses GrootPolicy.from_pretrained directly (same as lerobot-record)
and loads preprocessors from checkpoint.

Usage (on Jetson):
  /opt/digital-twin/venv/bin/python3 /tmp/groot_offline_eval.py
"""

import torch
import numpy as np

MODEL_PATH = "/opt/digital-twin/models/groot_1"
DATASET_REPO = "nacho92sa/color_blocks_all"


def main():
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from lerobot.policies.groot.modeling_groot import GrootPolicy
    from lerobot.policies.factory import make_pre_post_processors

    print("Loading dataset...")
    ds = LeRobotDataset(DATASET_REPO)
    print(f"  {len(ds)} frames")

    print("\nLoading policy (from_pretrained)...")
    policy = GrootPolicy.from_pretrained(MODEL_PATH)
    policy.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    policy.to(device)
    print(f"  On {device}")

    print("\nBuilding processors...")
    preprocessor, postprocessor = make_pre_post_processors(
        policy.config,
        pretrained_path=MODEL_PATH,
        dataset_stats=ds.meta.stats,
    )

    test_indices = [0, 50, 100, 500, 1000, 2000]

    for idx in test_indices:
        if idx >= len(ds):
            continue

        sample = ds[idx]
        ep = sample.get("episode_index", -1)
        frame = sample.get("frame_index", -1)
        actual = sample["action"].numpy()

        batch = preprocessor(sample)
        # Preprocessor already adds batch dim for some keys; just move to device
        batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v
                 for k, v in batch.items()}

        with torch.no_grad():
            pred_raw = policy.predict_action_chunk(batch)

        # pred_raw may be (horizon, action_dim) or (1, horizon, action_dim)
        p = pred_raw.cpu().numpy()
        if p.ndim == 3:
            pred_first = p[0, 0, :6]
        else:
            pred_first = p[0, :6]

        print(f"\nFrame idx={idx} (ep={ep}, frame={frame}):")
        print(f"  Actual:     [{', '.join(f'{x:8.3f}' for x in actual[:6])}]")
        print(f"  Pred (raw): [{', '.join(f'{x:8.3f}' for x in pred_first[:6])}]")

    # Variation test
    print(f"\n{'='*60}")
    print("Variation: frames 0-200 step 20")
    preds = []
    for idx in range(0, min(200, len(ds)), 20):
        sample = ds[idx]
        batch = preprocessor(sample)
        batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v
                 for k, v in batch.items()}
        with torch.no_grad():
            pred = policy.predict_action_chunk(batch)
        p = pred.cpu().numpy()
        preds.append(p[0, 0, :6] if p.ndim == 3 else p[0, :6])

    preds = np.array(preds)
    print(f"  Std per joint:   [{', '.join(f'{x:.4f}' for x in preds.std(axis=0))}]")
    for j in range(6):
        print(f"  Joint {j} range: [{preds[:, j].min():.4f}, {preds[:, j].max():.4f}]")


if __name__ == "__main__":
    main()
