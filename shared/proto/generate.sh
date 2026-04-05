#!/bin/bash
# Generate Python gRPC code from .proto files.
#
# HOW CODE GENERATION WORKS:
#   protoc (the protobuf compiler) reads .proto files and outputs:
#
#   1. *_pb2.py — message classes (TelemetryPoint, AlertEvent, etc.)
#      These are Python dataclasses-like objects with serialization.
#      Create them: point = TelemetryPoint(bucket="...", avg_value=42.0)
#      Serialize:   point.SerializeToString()
#
#   2. *_pb2_grpc.py — service stubs and base classes
#      - AnalyticsServiceServicer: base class the SERVER inherits from
#      - AnalyticsServiceStub: class the CLIENT uses to make calls
#
#   3. *_pb2.pyi — type stubs for IDE autocompletion
#
# WHEN TO RE-RUN:
#   Every time you change a .proto file. Generated files are committed
#   to git so not everyone needs grpcio-tools installed.
#
# USAGE:
#   cd shared/proto && bash generate.sh
#   OR from project root: bash shared/proto/generate.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTO_DIR="$SCRIPT_DIR"
OUT_DIR="$SCRIPT_DIR/../shared/generated"

mkdir -p "$OUT_DIR"

for PROTO_FILE in telemetry report; do
    python -m grpc_tools.protoc \
        --proto_path="$PROTO_DIR" \
        --python_out="$OUT_DIR" \
        --grpc_python_out="$OUT_DIR" \
        --pyi_out="$OUT_DIR" \
        "$PROTO_DIR"/${PROTO_FILE}.proto

    # Fix imports: protoc generates `import X_pb2` but inside a
    # package we need `from . import X_pb2` (relative import).
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/^import ${PROTO_FILE}_pb2/from . import ${PROTO_FILE}_pb2/" "$OUT_DIR/${PROTO_FILE}_pb2_grpc.py"
    else
        sed -i "s/^import ${PROTO_FILE}_pb2/from . import ${PROTO_FILE}_pb2/" "$OUT_DIR/${PROTO_FILE}_pb2_grpc.py"
    fi
done

echo "Generated gRPC code in $OUT_DIR"
