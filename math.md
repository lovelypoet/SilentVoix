Temporal Synchronization and Acceptance Thresholds
To ensure reliable alignment between computer vision (CV) data and dual-glove sensor streams, we define a quantitative synchronization procedure based on an explicit sync gesture and timestamped data. This section formalizes the spike detection criteria, temporal offsets, and acceptance thresholds used to validate captured samples.

Spike Detection
A synchronization spike is defined as a short-duration, high-magnitude event intentionally produced by the user (e.g., tap or forceful motion) and detectable across all modalities.
Sensor Stream Spike
For each glove sensor stream, let x(t)x(t)x(t) denote the scalar magnitude of the sensor signal (e.g., acceleration norm or aggregated pressure). Using a rolling pre-spike window, we compute the mean μ\muμ and standard deviation σ\sigmaσ.
A spike is detected when:
x(t)>μ+6σx(t) > \mu + 6\sigmax(t)>μ+6σ
and the condition persists for at least two consecutive sensor samples. This criterion minimizes false positives caused by noise while remaining robust to individual differences in motion strength.
CV Stream Spike
On the CV side, a spike is detected using hand landmark motion. Let vfv_fvf​ denote the hand velocity magnitude at frame fff, with rolling statistics vˉ\bar{v}vˉ and σv\sigma_vσv​.
A CV spike is detected when:
vf>vˉ+5σvv_f > \bar{v} + 5\sigma_vvf​>vˉ+5σv​
for at least two consecutive frames. The timestamp of this frame is treated as the global synchronization reference.

Temporal Offset Estimation
For each glove i∈{L,R}i \in \{L, R\}i∈{L,R}, the temporal offset relative to CV is computed as:
Δi=ti,spikesensor−tspikeCV\Delta_i = t^{\text{sensor}}_{i,\text{spike}} - t^{\text{CV}}_{\text{spike}}Δi​=ti,spikesensor​−tspikeCV​
This offset represents the alignment shift required to map sensor timestamps into the CV time domain.

Absolute Offset Acceptance Criteria
To detect invalid or poorly synchronized captures, the following thresholds are applied independently to each glove:
Acceptable:


∣Δi∣≤500 ms|\Delta_i| \le 500 \text{ ms}∣Δi​∣≤500 ms
Warning (usable with caution):


500<∣Δi∣≤2000 ms500 < |\Delta_i| \le 2000 \text{ ms}500<∣Δi​∣≤2000 ms
Reject:


∣Δi∣>2000 ms|\Delta_i| > 2000 \text{ ms}∣Δi​∣>2000 ms
Offsets greater than 2 seconds are considered implausible for an intentional synchronization gesture and indicate capture failure.

Inter-Glove Synchronization Constraint
To ensure consistency between left and right glove data, we define the inter-glove offset difference:
ΔLR=∣ΔL−ΔR∣\Delta_{LR} = |\Delta_L - \Delta_R|ΔLR​=∣ΔL​−ΔR​∣
The following thresholds are enforced:
High-quality synchronization:


ΔLR≤100 ms\Delta_{LR} \le 100 \text{ ms}ΔLR​≤100 ms
Acceptable with warning:


100<ΔLR≤300 ms100 < \Delta_{LR} \le 300 \text{ ms}100<ΔLR​≤300 ms
Reject:


ΔLR>300 ms\Delta_{LR} > 300 \text{ ms}ΔLR​>300 ms
An inter-glove delta exceeding 300 ms indicates that the synchronization gesture was not simultaneously captured by both gloves, compromising multimodal fusion.

Final Sample Validation Rule
A sample is automatically accepted if:
a CV spike is detected,


both glove streams contain a valid spike,


∣ΔL∣≤500|\Delta_L| \le 500∣ΔL​∣≤500 ms,


∣ΔR∣≤500|\Delta_R| \le 500∣ΔR​∣≤500 ms,


ΔLR≤300\Delta_{LR} \le 300ΔLR​≤300 ms.


Samples violating hard thresholds are rejected, while samples within warning ranges are retained but flagged in metadata for downstream analysis.

Metadata Logging
All synchronization metrics are stored alongside each sample to ensure transparency, reproducibility, and dataset auditability. Logged fields include spike timestamps, offsets, inter-glove deltas, and synchronization quality labels.