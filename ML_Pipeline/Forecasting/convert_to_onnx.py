import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from skl2onnx import convert_sklearn, update_registered_converter
from skl2onnx.common.data_types import FloatTensorType
import onnxruntime as rt

# Import LightGBM converters from onnxmltools
from onnxmltools.convert.common.shape_calculator import calculate_linear_regressor_output_shapes
from onnxmltools.convert.lightgbm.operator_converters.LightGbm import convert_lightgbm

# 1. Register LightGBM with skl2onnx
update_registered_converter(
    LGBMRegressor, 'LightGbmLGBMRegressor',
    calculate_linear_regressor_output_shapes, convert_lightgbm
)

# 2. Load the finalized model
print("Loading stability_model_v2_final.joblib...")
pipeline = joblib.load("stability_model_v2_final.joblib")

# 3. Define the exact features used by the model
features = [
    'compute_potential', 'delta_p_7d', 'delta_p_14d', 'delta_p_1d', 
    'vol_30d', 'official_egp_usd', 'cpi_inflation', 'is_major_sale_period', 
    'competitor_scarcity_count', 'volume_weight', 'D_months', 'k', 
    'import_lambda', 'missing_release_date'
]
initial_type = [(f, FloatTensorType([None, 1])) for f in features]

# 4. Convert to ONNX
print("Converting Pipeline to ONNX format...")
onx = convert_sklearn(pipeline, initial_types=initial_type, target_opset={'': 12, 'ai.onnx.ml': 3})

# 5. Save the model
onnx_filename = "stability_model_v2.onnx"
with open(onnx_filename, "wb") as f:
    f.write(onx.SerializeToString())
print(f"ONNX model saved as: {onnx_filename}")

# 6. Verification (Inference Test)
print("Verifying ONNX output vs Joblib output...")
data = np.random.randn(5, 14).astype(np.float32)
df_dummy = pd.DataFrame(data, columns=features)

# Joblib prediction
joblib_pred = pipeline.predict(df_dummy)

# ONNX prediction
sess = rt.InferenceSession(onnx_filename, providers=['CPUExecutionProvider'])
onnx_inputs = {f: data[:, i:i+1] for i, f in enumerate(features)}
label_name = sess.get_outputs()[0].name
onnx_pred = sess.run([label_name], onnx_inputs)[0].flatten()

# Check residual
diff = np.abs(joblib_pred - onnx_pred).max()
print(f"Max residual: {diff:.8f}")
if diff < 1e-4:
    print("Verification SUCCESS: Joblib and ONNX results are identical (within tolerance).")
else:
    print("Verification WARNING: Significant difference detected.")
