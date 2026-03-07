let latestFusionCaptureArtifact = null

export function setLatestFusionCaptureArtifact(artifact) {
  latestFusionCaptureArtifact = artifact || null
}

export function getLatestFusionCaptureArtifact() {
  return latestFusionCaptureArtifact
}

export function clearLatestFusionCaptureArtifact() {
  latestFusionCaptureArtifact = null
}
