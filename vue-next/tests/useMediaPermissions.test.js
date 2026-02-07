import { setActivePinia, createPinia } from 'pinia';
import { useMediaPermissions } from '../src/composables/useMediaPermissions';
import { useTrainingSettings } from '../src/composables/useTrainingSettings';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { nextTick } from 'vue';

// Mock the global navigator object
global.navigator.mediaDevices = {
  getUserMedia: vi.fn(),
};

describe('useMediaPermissions', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('should not request permissions if camera is not enabled', async () => {
    const { requestPermissions, stream } = useMediaPermissions();
    const settings = useTrainingSettings();
    settings.enableCamera.value = false;

    await requestPermissions();


    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
    expect(stream.value).toBeNull();
  });

  it('should request permissions and set stream when camera is enabled', async () => {
    const mockStream = { getTracks: () => [{ stop: vi.fn() }] };
    navigator.mediaDevices.getUserMedia.mockResolvedValue(mockStream);

    const { requestPermissions, stream, hasPermissions } = useMediaPermissions();
    const settings = useTrainingSettings();
    settings.enableCamera.value = true;

    await requestPermissions();

    expect(stream.value).toStrictEqual(mockStream);
    expect(hasPermissions.value).toBe(true);
  });

  it('should handle permission request error', async () => {
    const mockError = new Error('Permission denied');
    navigator.mediaDevices.getUserMedia.mockRejectedValue(mockError);

    const { requestPermissions, stream, hasPermissions, error } = useMediaPermissions();
    const settings = useTrainingSettings();
    settings.enableCamera.value = true;

    await requestPermissions();

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
    expect(stream.value).toBeNull();
    expect(hasPermissions.value).toBe(false);
    expect(error.value).toBe(mockError);
  });

  it('should stop the stream', async () => {
    const mockTrack = { stop: vi.fn() };
    const mockStream = { getTracks: () => [mockTrack] };
    navigator.mediaDevices.getUserMedia.mockResolvedValue(mockStream);

    const { requestPermissions, stopStream, stream } = useMediaPermissions();
    const settings = useTrainingSettings();
    settings.enableCamera.value = true;

    await requestPermissions();
    expect(stream.value).toStrictEqual(mockStream);

    stopStream();

    expect(mockTrack.stop).toHaveBeenCalled();
    expect(stream.value).toBeNull();
  });

  it('should re-request permissions when selected camera changes', async () => {
    const { requestPermissions } = useMediaPermissions();
    const settings = useTrainingSettings();
    settings.enableCamera.value = true;

    await requestPermissions();

    navigator.mediaDevices.getUserMedia.mockClear();

    settings.selectedCamera.value = 'new-camera-id';
    await nextTick();

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
  });

  it('should re-request permissions when resolution changes', async () => {
    const { requestPermissions } = useMediaPermissions();
    const settings = useTrainingSettings();
    settings.enableCamera.value = true;

    await requestPermissions();

    navigator.mediaDevices.getUserMedia.mockClear();

    settings.resolution.value = '720p'; // Assuming '1080p' is the default
    await nextTick();

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
  });
});
