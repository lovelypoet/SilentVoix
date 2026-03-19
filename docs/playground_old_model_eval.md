# Playground vs Old YOLO+LSTM Model

## Purpose

This note checks whether the old YOLO+LSTM model is inherently broken, or whether the current playground is feeding it the wrong inference contract.

## Old Model Contract

Source reviewed:
- [Code_yololstm.py](/home/lystiger/Documents/SilentVoix/docs/referrences/Code_yololstm.py)
- [metadata6.json](/home/lystiger/Documents/SilentVoix/AI/models/metadata6.json)

The old model is a temporal CV classifier with this contract:

- Model family: `lstm`
- Modality: `cv`
- Sequence length: `16`
- Feature dim per frame: `63`
- Total flattened input dim: `1008`
- Preprocess profile: `cv_wrist_center_v1_scaled`
- Labels:
  `Goodbye`, `Hello`, `No`, `Thank you`, `Yes`

Important implementation details from the old pipeline:

- It uses YOLO hand detection first.
- It crops the detected hand region.
- It applies MediaPipe on the crop.
- It keeps only the first detected hand.
- It builds a temporal sequence of `16` frames.
- Each frame contributes `63` values.

Conclusion:
The old model is not a single-frame classifier. It is a sequence classifier.

## Current Playground Contract

Relevant files reviewed:
- [useInferencePipeline.js](/home/lystiger/Documents/SilentVoix/vue-next/src/composables/ai/useInferencePipeline.js)
- [playgroundStore.js](/home/lystiger/Documents/SilentVoix/vue-next/src/stores/playgroundStore.js)
- [gesture_service.py](/home/lystiger/Documents/SilentVoix/services/gesture_service.py)
- [predict_integrated_routes.py](/home/lystiger/Documents/SilentVoix/api/routes/predict_integrated_routes.py)
- [model_library_routes.py](/home/lystiger/Documents/SilentVoix/api/routes/model_library_routes.py)

The current CV playground path does this:

- Takes only `hands[0]`
- Flattens a single frame into `63` values
- Sends `{ cv_values: vector }`
- Does not build a `16`-frame sequence in the frontend path

That means the current frontend playground does not match the old model contract.

## Additional Architecture Problem

The mounted API router in [model_library_routes.py](/home/lystiger/Documents/SilentVoix/api/routes/model_library_routes.py) currently handles model upload/list/activate/delete, but it does not expose the old `/model-library/predict/cv` inference route that the frontend still calls from [api.js](/home/lystiger/Documents/SilentVoix/vue-next/src/services/api.js).

So there are two separate issues:

1. The current playground input shape does not match the old model.
2. The current mounted API path is incomplete for that old playground inference call.

## What Still Matches the Old Model

The integrated gesture path in [gesture_service.py](/home/lystiger/Documents/SilentVoix/services/gesture_service.py) is closer to the old model contract:

- default `sequence_length = 16`
- default `feature_dim = 63`
- temporal frame buffer exists
- remote classifier path flattens buffered sequence for runtime inference

So the integrated path is conceptually closer to the old YOLO+LSTM design than the current model-library playground CV path.

## Verdict

Most likely cause of poor old-model behavior:

- the current playground, not the old model itself

Reason:

- old model expects `16 x 63`
- current playground sends `63`
- old model depends on temporal context
- the currently mounted model-library API path is not aligned with the frontend inference call

This does not prove the old model is perfect. It only shows the current playground is not a fair evaluation environment for it.

## Recommended Evaluation Method

To evaluate the old model correctly:

1. Replay known feature sequences shaped as `16 x 63`.
2. Run them through the same runtime contract used by the old model.
3. Compare offline prediction results against playground/backend results.
4. Add debug logs for:
   `buffer length`, `feature dim`, `flattened dim`, `active model metadata`, `sequence_length`.

## Practical Next Step

Before judging old sequence models, fix the playground to support:

- buffered temporal inference
- sequence-aware model routing
- metadata-driven shape handling
- a working inference route for uploaded CV models

Only after that should old LSTM model quality be re-evaluated.
