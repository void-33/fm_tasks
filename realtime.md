# DarkStream: Real-Time Speech Anonymization Architecture

**Source:** Quamer, W. & Gutierrez-Osuna, R. "DarkStream: real-time speech anonymization with low latency." Accepted for presentation at ASRU 2025. arXiv:2509.04667

---

## 1. Overview


The system consists of four main modules:

1. **Content encoder** — produces linguistic (speaker-independent) embeddings from raw audio
2. **k-means bottleneck** — optional quantization step that strips residual speaker cues
3. **Speaker/variance adapter** — injects a target (anonymized) speaker identity and prosody into the content stream
4. **Decoder / neural vocoder** — synthesizes the final waveform directly, with no intermediate mel-spectrogram

A separate **GAN-based speaker generator** produces the pseudo-speaker embeddings used for anonymization.

### 1.1 Full pipeline 

```
RAW AUDIO WAVEFORM
shape: [T]  (T = num samples, 16kHz, mono, float32)
        |
        +---------------------+----------------------+
        |                                             |
        v                                             v
CONTENT ENCODER                              SPEAKER ENCODERS
(causal CNN + lookahead                     (X-vector + ECAPA-TDNN,
 + causal self-attention)                    run on full utterance)
        |                                             |
        v                                             v
CONTENT EMBEDDINGS                          SPEAKER EMBEDDING (real)
shape: [T/320, 512]                         shape: [704] (512-d X-vector
(~20ms/frame, 320x                           concat 192-d ECAPA-TDNN,
 downsample from raw audio)                  one vector per utterance)
        |                                             |
        |                                             v
        |                                  GAN GENERATOR (WGAN-QC)
        |                                  in : noise z, shape [16]
        |                                  out: PSEUDO-SPEAKER EMBEDDING
        |                                       shape: [704]
        |                                  (rejected if cosine similarity
        |                                   to original >= 0.65)
        |                                             |
        +---------------------+----------------------+
                              |
                              v
              SPEAKER / VARIANCE ADAPTER
        (AdaIN/FiLM: gamma, beta from speaker
         vector applied to instance-normalized
         content; + F0 predictor + energy predictor)
                              |
                              v
              ADAPTED CONTENT EMBEDDINGS
              shape: [T/320, 512]
                              |
                              v
              DECODER CONTEXT LAYER
        (causal MHSA, 2s lookback window)
                              |
                              v
              HIFI-GAN STYLE VOCODER
      (transposed causal convs, upsample [8,5,4,2] = 320x)
                              |
                              v
             ANONYMIZED AUDIO WAVEFORM
             shape: [T]  (16kHz, mono, float32)
```

---

## 2. Content Encoder

**Purpose:** transform raw waveform into a sequence of 512-dimensional, speaker-independent embeddings representing localized linguistic units, while respecting real-time/causal constraints.

Composed of three sequential sub-blocks: **CNN encoder → lookahead layer → contextual (MHSA) layer**.

### 2.1 CNN Encoder

- Adapted from the HiFi-GAN encoder, modified for streaming.
- All transposed convolutions replaced with **strided causal convolutions** — each block sees only past and current audio, never future audio.
- **1 residual block** (a lighter version vs. 3 in prior work), downsampling rates **[2, 4, 5, 8]** → total downsampling factor of **320**, producing one 512-dim vector per output frame (~20ms/frame at 16kHz).
- Kernel size 5, dilations **[[1,1],[3,1],[5,1]]** — captures short-term acoustic patterns for phonetic discrimination.
- Functionally: performs local feature extraction *and* downsampling simultaneously (not just downsampling) — outputs are already meaningful local acoustic/phonetic representations.
- Limitation: purely causal, so it has no way to represent forward coarticulation (how a sound is shaped by what comes *after* it) — motivates the lookahead layer.

**Alternate front-end — Mel-spectrogram encoder:**
- Input converted to a 160-bin Mel spectrogram (16kHz audio, 1024-sample FFT window, 320-sample hop).
- Processed by a lightweight **ConvNeXt** encoder (reduced to layer config [1,1,3,1]) instead of the HiFi-style CNN, producing 512-dim embeddings at the same 20ms frame rate.
- Downstream blocks (lookahead, contextual layer) are unchanged regardless of which front-end is used.
- Trade-off: more robust to channel noise, slightly different latency/quality profile vs. raw-waveform front-end.

### 2.2 Lookahead Layer

- A single **1D convolutional layer**, non-causal, placed directly after the CNN encoder.
- Receptive field extends **up to 280ms into the future** (configurable — 0/20/60/140/280ms tested).
- Does **not** downsample — same frame rate in and out.
- Purpose: inject short-term future context so the model can represent anticipatory coarticulation effects (e.g., how a vowel's articulation shifts in preparation for the following consonant).
- This is the model's sole source of algorithmic (buffering) latency in the encoder — it is the only block that must wait for audio that hasn't arrived yet.
- Architecturally distinct from the CNN encoder despite both being convolutional: CNN encoder is deep, causal, downsampling; lookahead layer is shallow, non-causal, resolution-preserving.

### 2.3 Contextual Layer

- Stack of **8 causal multi-head self-attention (MHSA) layers**.
- Causal masking + fixed **2-second past context window**.
- Purpose: model long-range dependencies across the sequence — lets each frame's representation be refined using earlier context in the utterance (disambiguation, propagation of consistent linguistic structure).
- Does **not** add latency, because the 2-second window is backward-looking (already-processed audio), not forward-looking.
- **Ring KV cache**: stores previously computed key/value vectors per frame so attention is computed incrementally (O(1) per new frame) rather than recomputed over the full window each time. Cache is zero-initialized and fills to capacity over the first 2 seconds of a stream (causing a brief accuracy ramp-up at stream start, not a latency cost).

### 2.4 Output

The final 512-dim **content embedding** per frame is the output of the *entire* three-stage stack (CNN → lookahead → MHSA), not any single sub-block in isolation. Ablations (Table I in the paper) show each stage contributes independently — removing the contextual layer or the lookahead both measurably reduce token-ID prediction accuracy.

---

## 3. Training the Content Encoder — HuBERT + k-means Pseudo-Labels

The content encoder is trained as a **200-way frame classifier** using cross-entropy loss, since there is no direct ground-truth "correct embedding" to regress against.

**Generating target labels (done once, offline, before/during training):**
1. Run pretrained **HuBERT-base** over training audio, extract continuous hidden vectors from the **9th transformer layer**.
2. Fit **k-means with 200 centroids** on these HuBERT vectors across the training corpus.
3. For every frame, its pseudo-label = index of the nearest of the 200 centroids to that frame's HuBERT vector.

**Training loop:**
```
raw audio --[content encoder]--> 512-dim embedding (per frame)
                                        |
                          [linear layer: 512 -> 200] -> softmax
                                        |
                              predicted class distribution
                                        |
                      cross-entropy loss vs. pseudo-label (0-199)
```
This distills HuBERT's (non-causal, non-streaming) clustering behavior into a lightweight causal model, without requiring HuBERT at inference time. The classifier head (linear + softmax) is typically discarded after training; only the 512-dim embeddings are used downstream.

**Generalization:** because phonetic categories (coarticulation patterns, sub-phonetic sound units) recur across sentences and speakers, a model trained this way on a large diverse corpus generalizes to unseen sentences — it isn't memorizing text, it's recognizing recurring local sound categories.

---

## 4. k-means Bottleneck (Privacy Mechanism)

A **second, unrelated** k-means step — clusters DarkStream's own 512-dim content embeddings (not HuBERT's), with **256 centroids**, fit after the content encoder is trained.

**Mechanism:**
- At inference, each frame's continuous 512-dim embedding is snapped to its nearest of 256 fixed codebook points.
- This acts as a hard information bottleneck: fine-grained continuous variation (where residual speaker-specific cues like subtle pronunciation habits tend to hide) is discarded, while coarser phonetic distinctions (needed for intelligibility) are mostly preserved.
- Optional — trades some synthesis quality/naturalness for a significant anonymization gain.

**Measured effect (VoicePrivacy Challenge 2024 metrics):**
- Lazy-informed attacker EER rises to ~46–47% (near chance) with quantization enabled.
- WER roughly doubles (e.g., 13.9% at 0ms lookahead) compared to the unquantized case — the cost of discretization, including reduced generalization to sentence patterns/phonetic sequences not well represented in the training corpus's codebook.

---

## 5. Speaker Representation and Anonymization

### 5.1 Speaker Encoders

- Real speaker identity is derived by **concatenating** embeddings from two pretrained encoders:
  - **X-vector** (512-dim, noise-robust)
  - **ECAPA-TDNN** (192-dim, context-sensitive)
- Combined into a **704-dim** speaker embedding per utterance (not per-frame).
- Pretrained checkpoints sourced from SpeechBrain.

### 5.2 GAN-based Pseudo-Speaker Generator (WGAN-QC)

**Why it's needed even though its output (not the real speaker embedding) is what gets injected:**
1. **Training the GAN** requires real speaker embeddings as the target distribution the generator must learn to imitate.
2. **Training the speaker/variance adapter** requires real speaker embeddings as realistic conditioning vectors (the adapter never sees GAN-generated vectors during training).
3. **Inference-time similarity check** — the real speaker embedding of the current input speaker is still extracted so a sampled pseudo-speaker embedding can be rejected if it's too similar to the original (see below).

**Generator (G):**
- Input: 16-dim noise vector `z`.
- Linear layer → 192-dim → reshaped to 3×8×8 tensor.
- Two ResNet blocks → two stages of 2× upsampling with ResNet blocks → two final ResNet blocks.
- Flattened and linearly projected to a **704-dim** pseudo-speaker embedding.

**Critic (D):** mirrors the generator in reverse — expands 704-dim input to a 3×8×8 tensor, two ResNet blocks, two downsampling stages (2× average pooling + ResNet blocks), flattened to a scalar score.

**Objective (WGAN-QC with gradient penalty):**
```
L_D = E[D(real)] - E[D(G(z))] + 10 * E[||∇D(interpolated)||²]
L_G = -E[D(G(z))]
```

**Inference-time sampling and rejection:**
- Sample `e_syn = G(z)`.
- Reject any sample whose cosine similarity to the real (original) speaker embedding is **≥ 0.65** — ensures the pseudo-speaker embedding is both realistic (learned via the GAN) and sufficiently dissimilar to the true speaker (the actual anonymization guarantee).

### 5.3 Speaker/Variance Adapter

- Integrates speaker identity and prosody (pitch, energy) into speaker-agnostic content embeddings.
- Content embeddings first pass through **instance normalization** to strip residual speaker cues.
- Two causal 1D CNNs, conditioned on the (pseudo-)speaker embedding, generate frame-level **scale (γ) and shift (β)** parameters, applied via **AdaIN/FiLM conditioning** to re-color the normalized content with the target speaker's timbre.
- Separate lightweight blocks (2-layer causal CNN, kernel=3, ReLU, layer norm, dropout, pointwise conv) predict **F0** and **energy** trajectories, supervised during training against ground-truth values; at inference, predictions are fed directly into the feature stream for explicit pitch/loudness control.
- Output: **adapted content embeddings**, same shape as input ([T/320, 512]) — only the values are re-colored, not the shape.

---

## 6. Decoder / Neural Vocoder

Converts the adapted embedding sequence directly into a time-domain waveform, in two internal steps — with **no intermediate mel-spectrogram** at inference (this is DarkStream's key departure from offline pipelines).

**Step 1 — Context layer:** a causal MHSA block (same style as the content encoder's contextual layer), 2-second look-back window, adds long-range temporal coherence to the adapted embeddings before synthesis.

**Step 2 — HiFi-GAN-style generator:** stack of upsampling transposed causal convolutions, upsample rates **[8, 5, 4, 2]** (= 320×, mirroring the encoder's downsampling), residual blocks with kernel size 5, dilations [[1,1],[3,1],[5,1]], progressively reconstructing 16kHz audio.

**Training objective:** mel-spectrogram reconstruction loss (training-time signal only — never computed at inference) + multi-scale and multi-period waveform discriminators + multi-resolution spectrogram discriminator (same discriminator setup as the DAC/RVQGAN neural codec).

**Comparison to offline pipelines:**

| | Offline | DarkStream (streaming) |
|---|---|---|
| Path | adapted embeddings → acoustic model → mel-spectrogram → vocoder → waveform | adapted embeddings → context layer → vocoder → waveform |
| Intermediate mel-spectrogram at inference | Yes | No |
| Stages | 2 (separately trained/optimized) | 1 (context + vocoder trained jointly) |

---

## 7. Training Setup

- **Content encoder + decoder**: trained on **LibriTTS** (train subsets, ~600hrs), individually for 1.2M steps each, AdamW optimizer, LR 5e-4, batch size 16 (random 2–4s clips), NVIDIA RTX 3090.
- **GAN speaker generator**: trained on **CommonVoice (English)** for diverse voice coverage.
- **k-means bottleneck fine-tuning**: when enabled, content encoder is frozen, k-means run on its outputs to build the 256-centroid codebook, then decoder (and partially the adapter) fine-tuned on quantized inputs for an additional 300k steps.
- **Evaluation**: VoicePrivacy Challenge 2024 evaluation subsets — LibriTTS dev-clean/test-clean (intelligibility, privacy) and IEMOCAP-derived emotional speech (emotion preservation).

---

## 8. Latency and Performance Summary

**Chosen default configuration:** waveform front-end + contextual layer + 140ms lookahead — captures ≈99% of non-causal token accuracy while keeping end-to-end latency within a 350ms budget.

| Metric (140ms LA, Wave+CL) | Value |
|---|---|
| Encoder-only latency (GPU) | ~189ms |
| End-to-end latency (GPU) | ~203ms |
| Real-time factor (GPU) | ~0.005 (≈200× faster than real-time) |
| Real-time factor (CPU) | 0.258 (≈4× faster than real-time) |
| WER (no quantization) | 2.09% |
| WER (with 256-centroid quantization) | 9.52% |
| EER, lazy-informed (no quantization) | 12.10% |
| EER, lazy-informed (with quantization) | 46.75% (near chance) |
| MOS (Wav+CL, no quantization) | 3.79 (vs. 3.90 original) |
| MOS (Wav+CL, with quantization) | 3.22 |

**Comparison to VoicePrivacy Challenge 2024 baselines (semi-informed attacker):** DarkStream achieves 22.68% EER, closely matching offline baselines B3 (26.28%) and B5a (22.09%) — despite requiring only a 140ms lookahead versus baselines that require the full utterance.

---

## 9. Known Limitations 

- Does not explicitly disentangle **static speaker traits** (accent, age, sex) from **dynamic attributes** (emotion, speaking style) — some indirect identity cues may remain intact even after anonymization.
- Future directions noted by the authors: explicit static/dynamic attribute disentanglement, controllable anonymization (selectable sex/accent), introduction of filler words/style modification to mask habitual speech patterns, and further optimization for lightweight CPU deployment.

















































Proposed Use Case and Impact

Use Case. ------ is a real-time voice privacy layer for Nepali-language tele-counseling and mental health helplines. A client speaks naturally into the call; the counselor hears the same words, carrying the same emotional state, in a different voice. Speaker identity is concealed from the counselor and from any stored recording, while intelligibility and affect — the counselor's primary clinical instrument — are preserved. Anonymity is scoped to the session, with a policy-controlled escalation path so the service can still act when a caller is at risk.

Impact. Nepal's mental health treatment gap exceeds 90%, and among the most commonly reported barriers to treatment are fear of being perceived as "weak" for having mental health problems and fear of being perceived as "crazy" — barriers that a community survey found did not vary by age, sex, education, or caste/ethnicity. With roughly 0.22 psychiatrists per 100,000 people and under 1% of the health budget allocated to mental health, teletherapy is not a convenience but the only channel capable of reaching beyond urban centres. Voice, however, is identifying, and in Nepal's closely connected social and professional networks the fear of being recognized by a counselor is well founded. By removing recognition risk from the delivery channel that carries the therapeutic relationship, SwarChhaya addresses a named barrier to help-seeking rather than a hypothetical one — and the same system, run in batch mode, allows anonymized helpline archives to be released for supervision, training, and Nepali speech research that is presently impossible. 
