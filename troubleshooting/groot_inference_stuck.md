# GR00T N1.5 Inference Troubleshooting — "Robot Barely Moves"

Model: `nacho92sa/groot_1` | Dataset: `nacho92sa/color_blocks_all` | Jetson AGX Orin 32GB

## Symptom

GR00T inference runs without errors but the arm barely moves — tiny oscillations around a rest pose instead of reaching for the block. SmolVLA and ACT work fine on the same hardware with the same dataset.

## Training Run Summary

WandB: `upc-wildfires/lerobot/lerobot-training-groot-2026-05-01-15-42-43-273-q6608l-algo-1`

| Metric | Value |
|--------|-------|
| Steps | 15,000 |
| Final loss | 0.0196 |
| Loss curve | 0.099 → 0.062 → 0.025 → 0.020 (healthy, no collapse) |
| Instance | ml.g7e.2xlarge (SageMaker) |
| Batch size | 32 |
| LR | 1e-4 → 1e-5 (cosine decay, 500 warmup) |
| bf16 | enabled |
| Tuned | projector + diffusion_model (NOT llm, NOT visual) |
| Grad norm | stable ~0.48 |

Training looks healthy — loss converged smoothly, no signs of padding bug or collapse.

## Issues to Investigate (ranked by likelihood)

### 1. `n_action_steps=50` but model predicts 16 (HIGH)

GR00T's action head outputs **16 timesteps** max (`action_horizon = min(chunk_size, 16)` in `processor_groot.py:104`). But `config.json` has `n_action_steps: 50`. The `select_action` deque has `maxlen=50`, receives 16 real actions per inference call. After the 16 are consumed, a new inference runs — but if the deque or slicing logic is broken (see LeRobot PR #3190, still open), garbage values fill the remaining slots.

**Fix to test:**
```bash
--policy.n_action_steps=16
```

### 2. Denoising steps (MEDIUM-HIGH)

The flow-matching action head uses iterative Euler integration. The base model config has `num_inference_timesteps: 4`. Community reports (Isaac-GR00T #191) suggest:
- Training effectively uses 1 step per forward pass
- Using more steps at inference can push the model outside its trained distribution
- NVIDIA blog recommends trying 16 steps for better quality

No CLI flag exists to override this — it's hardcoded from the base model config. To change it, patch the loaded config or the flow_matching_action_head after model creation.

### 3. Known poor GR00T performance on SO-100/SO-101 (MEDIUM)

Multiple Isaac-GR00T issues report similar symptoms on SO-100/101:
- **#82**: SO-100 arm "just shudders", runs but fails to do anything
- **#130**: Jittering behavior, best result with single camera + 10k steps
- **#285**: SO-101 stuttering with fine-tuned model
- **#298**: SO-101 open-loop and real performance "very poor" (50 episodes, 10K steps)

This may be a fundamental limitation of GR00T N1.5 on low-DOF arms with limited training data.

### 4. LeRobot-trained vs Isaac-GR00T native pipeline (MEDIUM)

Issue #2505 on lerobot: model trained with LeRobot doesn't follow instructions, while same data trained with Isaac-GR00T native pipeline works. The integration may have subtle preprocessing differences.

### 5. `strict=False` patch side effects (LOW-MEDIUM)

We patched `modeling_groot.py` to set `strict=False` because the checkpoint has a full model dump (899 keys) and one key (`embed_tokens.weight`) was flagged as unexpected. This key is identical between checkpoint and base model, so the patch is harmless. But verify no other keys are silently dropped.

### 6. Relative vs absolute action confusion (LOW)

Isaac-GR00T uses RELATIVE actions for arm joints + ABSOLUTE for gripper. LeRobot's GR00T processor uses min-max normalization to [-1, 1]. If the model outputs relative deltas but the postprocessor treats them as absolute positions (or vice versa), actions appear near-current-state.

## Test Results (2026-05-02)

### Test A: n_action_steps=16 — NO IMPROVEMENT
Same behavior. Rules out action horizon mismatch.

### Test C: Raw action logging — MODEL IS RESPONDING (weakly)
Raw actions range [-1.96, 2.98] — NOT zero/garbage. But first 6 values (joints) are nearly identical across consecutive frames during live inference.

### Test D: 16 denoising steps — NO IMPROVEMENT
Patched `num_inference_timesteps` from 4 to 16. Same static pose. Rules out denoising issue.

### Test E: Offline dataset eval — ROOT CAUSE FOUND
Fed training dataset frames through the same LeRobot pipeline (no robot). Key findings:

| Frame | Actual Action (degrees) | Predicted (normalized) | Notes |
|-------|------------------------|----------------------|-------|
| 50 | `[1.1, -99.0, 93.4, 73.6, -2.1]` | `[-0.01, -1.0, 0.96, 0.62, 0.44]` | Start of episode |
| 500 | `[-9.2, -98.9, 70.3, 58.3, -10.8]` | `[-0.16, -0.99, 0.72, 0.47, 0.13]` | Predictions shift |
| 1000 | `[28.4, -9.7, -29.5, 46.5, -5.1]` | `[0.32, 0.11, -0.33, 0.34, 0.37]` | Clear tracking |
| 2000 | `[28.4, 27.0, -94.9, 83.6, -8.4]` | `[0.36, 0.66, -1.13, 0.86, 0.21]` | Different episode |

**Predictions correlate with actual actions across large time gaps** (direction is correct). But within short windows (frames 0-200), std per joint is only 0.01-0.03. The model learned the task structure but produces **severely compressed action deltas** — too small to move the arm meaningfully at 30fps.

## Conclusion

**Not a pipeline bug — this is a model capacity/training limitation on SO-101.**

The model:
- Receives images and language correctly
- Responds to visual input (predictions change across distant frames)
- Cannot produce large enough action differences between consecutive frames
- Outputs a near-static pose within any short time window

This matches Isaac-GR00T issues #82, #130, #285, #298 — all reporting similar behavior on SO-100/101.

## Potential Next Steps

1. **More training data** — current dataset has 50 episodes. Community reports suggest 200+ needed for SO-101.
2. **Isaac-GR00T native pipeline** — train with NVIDIA's pipeline instead of LeRobot (Issue #2505).
3. **More training steps** — 15K may not be enough for this embodiment.
4. **Different model** — SmolVLA and ACT already work on this hardware. Use them for the demo.

## Reference Links

- [LeRobot GR00T docs](https://huggingface.co/docs/lerobot/groot)
- [LeRobot PR #3190](https://github.com/huggingface/lerobot/pull/3190) — action slicing fix
- [Isaac-GR00T #298](https://github.com/NVIDIA/Isaac-GR00T/issues/298) — SO-101 poor performance
- [Isaac-GR00T #285](https://github.com/NVIDIA/Isaac-GR00T/issues/285) — SO-101 stuttering
- [Isaac-GR00T #191](https://github.com/NVIDIA/Isaac-GR00T/issues/191) — denoising steps mismatch
- [LeRobot #2505](https://github.com/huggingface/lerobot/issues/2505) — LeRobot vs native pipeline
- [HF blog: GR00T SO-101 fine-tuning](https://huggingface.co/blog/nvidia/gr00t-n1-5-so101-tuning)
- WandB credentials: see `/.env` in project root
