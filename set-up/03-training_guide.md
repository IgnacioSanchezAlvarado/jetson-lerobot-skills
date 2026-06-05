# LeRobot Training Guide for SO-101

Quick reference for finetuning 4 robot manipulation models on SO-101 arms.

## Model Comparison

| Model | Params | VLA? | Language? | Edge Hz (Jetson) | Steps | Batch Size | Best For |
|-------|--------|------|-----------|------------------|-------|------------|----------|
| ACT | 80M | No | No | 10-30 | 150k | 8 | Single-task, fast edge inference |
| SmolVLA | 450M | Yes | Yes | 1-2 | 30k | 64 | Multi-task edge, affordable hardware |
| Pi0.5 | 2.3B | Yes | Yes | 0.8-1.7 | 5k | 32-64 | High-quality, cloud/powerful GPU |
| GR00T N1.5 | 3B | Yes | Yes | Too large | 30k | 32 | NVIDIA ecosystem, bimanual tasks |

## 1. ACT (Action Chunking with Transformers)

**Profile**: 80M params, non-VLA, task-specific, fastest edge inference.

**Use When**: Single-task demos, need max speed on edge (10-30 Hz).

**Training Config**:
```bash
lerobot-train \
  --dataset.repo_id=${HF_USER}/your-dataset \
  --policy.type=act \
  --output_dir=outputs/train/act_your_dataset \
  --job_name=act_your_dataset \
  --policy.device=cuda \
  --wandb.enable=true
```

**Pretrained**: None — ACT trains from scratch on your dataset

**Notes**:
- One model per task (no language prompts)
- Fastest inference on Jetson
- Requires task-specific dataset per model

---

## 2. SmolVLA (Recommended for Jetson)

**Profile**: 450M params, VLA, designed for SO-100/101 + Jetson edge deployment.

**Use When**: Multi-task with language prompts, target affordable edge hardware.

**Training Config**:
```bash
cd lerobot && lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=your-org/your-dataset \
  --batch_size=64 \
  --steps=30000 \
  --save_freq=5000 \
  --output_dir=outputs/train/my_smolvla \
  --job_name=my_smolvla_training \
  --policy.device=cuda \
  --wandb.enable=true
```

**Pretrained**: `lerobot/smolvla_base`

**Notes**:
- Only ~50M params are actually finetuned (action expert + projections) — SigLIP vision encoder and SmolLM2 language model remain frozen
- Save checkpoints every 5k steps: `--save_freq=5000`
- Batch size 64 is recommended (use gradient accumulation if GPU memory limited)
- Official paper dataset: 50 episodes, 2 cameras (top+wrist), 30fps, 480x640
- Target performance: 78.3% multi-task success (SmolVLA paper)
- Edge inference: ~1-2 Hz on Jetson AGX Orin
- Best balance of capabilities vs. Jetson performance

---

## 3. Pi0.5 (Physical Intelligence)

**Profile**: 2.3B params, VLA, diffusion-based (flow matching), high-quality actions.

**Use When**: Need best action quality, have cloud/powerful GPU for inference.

**Training Config**:
```bash
lerobot-train \
  --dataset.repo_id=${HF_USER}/your-dataset \
  --policy.type=pi05 \
  --policy.pretrained_path=lerobot/pi05_base \
  --policy.compile_model=true \
  --policy.gradient_checkpointing=true \
  --policy.dtype=bfloat16 \
  --batch_size=32 \
  --steps=5000 \
  --output_dir=outputs/train/my_pi05 \
  --job_name=my_pi05_training \
  --policy.device=cuda \
  --wandb.enable=true
```

**Pretrained**: `lerobot/pi05_base`

**Notes**:
- Install Pi0.5 dependencies: `pip install -e ".[pi]"`
- `gradient_checkpointing=true` reduces memory significantly
- `compile_model=true` speeds up training
- `train_expert_only=true` option freezes VLM, trains only action expert (less memory)
- 10 diffusion denoising steps per prediction (reduce to 4 for speed at inference)
- Edge inference: ~0.8-1.7 Hz on Jetson (slow, reduce `num_inference_steps`)
- Best for cloud/datacenter deployment

---

## 4. GR00T N1.5 (NVIDIA)

**Profile**: 3B params, VLA, NVIDIA foundation model for humanoid/manipulation robotics.

**Use When**: Deep NVIDIA ecosystem integration, multi-camera setups, bimanual tasks.

**Training Config**:
```bash
lerobot-train \
  --dataset.repo_id=${HF_USER}/your-dataset \
  --policy.type=groot_n1 \
  --policy.pretrained_path=nvidia/GR00T-N1.5-3B \
  --policy.gradient_checkpointing=true \
  --batch_size=32 \
  --steps=30000 \
  --output_dir=outputs/train/my_groot \
  --job_name=my_groot_training \
  --policy.device=cuda \
  --wandb.enable=true
```

**Pretrained**: `nvidia/GR00T-N1.5-3B`

**Notes**:
- Now integrated into standard LeRobot training pipeline (no separate Isaac-GR00T repo needed)
- Requires flash-attention: `pip install flash-attn`
- `gradient_checkpointing=true` required for memory management at 3B params
- Libero benchmark: 87% average (82% spatial, 99% object, 82% long-horizon)
- Too large for Jetson AGX Orin 32GB inference in practice
- License: NVIDIA proprietary (Apache 2.0 starting from N1.7)

---

## Validating Before Training

Before starting a training run, validate your dataset to catch pipeline issues early:

**1. Visual inspection**: Use the HuggingFace dataset visualizer to plot joint positions and actions over time. Look for smooth curves, reasonable velocities, and gripper states matching what you see in the video. Irregularities indicate recording or pipeline issues.

```bash
# View dataset in browser
python -m lerobot.scripts.visualize_dataset --repo-id your-org/your-dataset
```

**2. Data replay** (most important step): Replay recorded episodes on the physical robot to verify actions are well-formatted and physically achievable. This catches issues that plots alone miss — bad action scaling, communication lag, coordinate mismatches.

```bash
# Replay episode 0 on the robot
python -m lerobot.scripts.replay_episode \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.cameras="{}" \
  --dataset.repo_id=your-org/your-dataset \
  --episode=0
```

If the replayed motion doesn't match what you recorded, your data has issues — fix before training.

**3. Stats validation**: Check `stats.json` in your dataset for physically plausible values. Action means and standard deviations should reflect your workspace dimensions. Watch for standard deviations of 0 (broken pipeline).

```python
import json
stats = json.load(open("data/your-dataset/meta/stats.json"))
print("Action mean:", stats["action"]["mean"])
print("Action std:", stats["action"]["std"])
# Std of 0 on any dimension = pipeline issue
assert all(s > 0 for s in stats["action"]["std"]), "Zero std detected!"
```

**Important**: Always use your own dataset's statistics at inference time — not the pretrained model's stats. Using mismatched statistics (e.g., from the LIBERO pretrained model) causes erratic arm behavior.

---

## Training Instance Recommendations

| Model | Recommended Instance | GPU | Time (est.) | Notes |
|-------|---------------------|-----|-------------|-------|
| ACT | ml.g6e.2xlarge | 1x L40S 48GB | ~2-3 hrs (150k steps) | Fast, small model |
| SmolVLA | ml.g7e.2xlarge | 1x L40S Tensor Core 48GB | ~45 min (30k steps) | Recommended for POCs |
| SmolVLA (local) | RTX 3090 | 1x RTX 3090 24GB | ~15 hrs (30k steps) | Consumer GPU option |
| Pi0.5 | ml.g7e.2xlarge | 1x L40S Tensor Core 48GB | ~45 min (5k steps) | 2.3B model, needs more VRAM |
| GR00T N1.5 | ml.g7e.2xlarge | 1x L40S Tensor Core 48GB | ~1 hr (30k steps) | 3B model, needs flash-attn |

---

## Common Training Issues

### 1. LeRobot Padding Bug (pre-0.4.5)
**Symptom**: Model learns to predict padded zeros, loss doesn't converge.

**Cause**: 
- Typo `action_is_pad` instead of `actions_is_pad` in loss masking
- Loss normalization divides by total elements (including masked zeros)

**Fix**: Use LeRobot >= commit after PR #3434 (April 23, 2026).

```bash
# Install latest from source
pip install git+https://github.com/huggingface/lerobot.git
```

### 2. Camera Key Mismatch
**Symptom**: Training works, inference crashes with KeyError.

**Fix**: Ensure dataset camera keys match model config exactly.

```python
# Check model config.json for expected camera keys
import json
config = json.load(open("path/to/model/config.json"))
print([k for k in config["input_features"] if "image" in k])
```

### 3. Batch Size Too Small
**Symptom**: Loss plateaus early, poor generalization.

**Fix**: Use batch size 64 directly for best results. If GPU memory limited, use gradient accumulation.

```bash
# Recommended: Direct batch size
--batch_size=64

# Alternative for limited GPU memory: Gradient accumulation
--batch_size=8 --gradient_accumulation_steps=8  # effective = 64
```

### 4. Evaluation Frequency
**Symptom**: Training crashes before checkpoint, lose progress.

**Fix**: Set `eval_freq` to save checkpoints regularly (every 5k-10k steps).

### 5. Wrong Statistics at Inference
**Symptom**: Erratic arm behavior — arm overshoots, jerks, or moves to unexpected positions despite good training loss.

**Cause**: Using the pretrained model's `stats.json` (from its original training data) instead of your finetuned dataset's statistics. Since `action_denorm = action * std + mean`, wrong stats produce wrong physical actions.

**Fix**: Ensure inference points to your finetuned checkpoint's stats, not the base model's. After training, verify the checkpoint directory contains a `stats.json` matching your dataset.

---

## Quick Start Example (SmolVLA)

```bash
# 1. Train on ml.g7e.2xlarge (~45min)
cd lerobot && lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=your-org/pick-red-block \
  --batch_size=64 \
  --steps=30000 \
  --save_freq=5000 \
  --output_dir=outputs/train/pick_red_block \
  --job_name=pick_red_block_training \
  --policy.device=cuda \
  --wandb.enable=true

# 2. Deploy to Jetson
# (Copy checkpoint, run lerobot-control with finetuned weights)
```

---

## Model Selection Decision Tree

```
Start here
    |
    ├─ Need language prompts for multi-task?
    |   ├─ No  → ACT (fastest, 10-30 Hz)
    |   └─ Yes → Continue
    |
    ├─ Deploy on Jetson edge?
    |   ├─ Yes → SmolVLA (1-2 Hz, designed for SO-100/101)
    |   └─ No  → Continue
    |
    ├─ Have powerful GPU (cloud)?
    |   ├─ Yes → Pi0.5 (best quality, 0.8-1.7 Hz on Jetson if needed)
    |   └─ No  → SmolVLA (affordable option)
    |
    └─ Deep NVIDIA ecosystem integration?
        └─ Yes → GR00T N1.5 (3B, cloud training, NVIDIA ecosystem)
```

---

## Resources

- LeRobot repo: https://github.com/huggingface/lerobot
- SmolVLA paper: https://arxiv.org/abs/2506.01844
- Pi0.5 (OpenPI): https://github.com/physicalintelligence/open-pi0
- GR00T N1.5: https://huggingface.co/nvidia/GR00T-N1.5-3B
- SO-100/101 arms: https://github.com/TheRobotStudio/SO-ARM100

---

## Notes for AWS Demos

- **SmolVLA** is the sweet spot for Jetson + SO-101 demos (1-2 Hz, multi-task, language).
- **ACT** if you need max speed and single-task is OK (10-30 Hz).
- **Pi0.5** for "best quality" cloud demos (show diffusion-based actions).
- **GR00T N1.5** if customer is NVIDIA-focused (now uses standard LeRobot pipeline).

Training cost for SmolVLA: ~45 min on ml.g7e.2xlarge (30k steps).
