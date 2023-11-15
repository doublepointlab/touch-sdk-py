# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: watch_output.proto
# Protobuf Python Version: 4.25.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import touch_sdk.protobuf.common_pb2 as common__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x12watch_output.proto\x1a\x0c\x63ommon.proto\"\xa8\x01\n\x04Info\x12\x18\n\x04hand\x18\x01 \x01(\x0e\x32\n.Info.Hand\x12\r\n\x05\x61ppId\x18\x02 \x01(\t\x12\x12\n\nappVersion\x18\x03 \x01(\t\x12\x1f\n\x0f\x61vailableModels\x18\x04 \x03(\x0b\x32\x06.Model\x12\x1b\n\x0b\x61\x63tiveModel\x18\x05 \x01(\x0b\x32\x06.Model\"%\n\x04Hand\x12\x08\n\x04NONE\x10\x00\x12\t\n\x05RIGHT\x10\x01\x12\x08\n\x04LEFT\x10\x02\"\x9e\x01\n\x0bSensorFrame\x12\x13\n\x04gyro\x18\x01 \x01(\x0b\x32\x05.Vec3\x12\x12\n\x03\x61\x63\x63\x18\x02 \x01(\x0b\x32\x05.Vec3\x12\x13\n\x04grav\x18\x03 \x01(\x0b\x32\x05.Vec3\x12\x13\n\x04quat\x18\x04 \x01(\x0b\x32\x05.Quat\x12\x12\n\x03mag\x18\x06 \x01(\x0b\x32\x05.Vec3\x12\x15\n\x06magCal\x18\x07 \x01(\x0b\x32\x05.Vec3\x12\x11\n\tdeltaTime\x18\x05 \x01(\x05\"8\n\x07Gesture\x12\x1a\n\x04type\x18\x01 \x01(\x0e\x32\x0c.GestureType\x12\x11\n\tdeltaTime\x18\x02 \x01(\x05\"\xd4\x01\n\nTouchEvent\x12-\n\teventType\x18\x01 \x01(\x0e\x32\x1a.TouchEvent.TouchEventType\x12\x13\n\x0b\x61\x63tionIndex\x18\x02 \x01(\x05\x12\x12\n\npointerIds\x18\x03 \x03(\x05\x12\x15\n\x06\x63oords\x18\x04 \x03(\x0b\x32\x05.Vec2\x12\x11\n\tdeltaTime\x18\x05 \x01(\x05\"D\n\x0eTouchEventType\x12\x08\n\x04NONE\x10\x00\x12\t\n\x05\x42\x45GIN\x10\x01\x12\x07\n\x03\x45ND\x10\x02\x12\x08\n\x04MOVE\x10\x03\x12\n\n\x06\x43\x41NCEL\x10\x04\".\n\x0bRotaryEvent\x12\x0c\n\x04step\x18\x01 \x01(\x05\x12\x11\n\tdeltaTime\x18\x02 \x01(\x05\",\n\x0b\x42uttonEvent\x12\n\n\x02id\x18\x01 \x01(\x05\x12\x11\n\tdeltaTime\x18\x02 \x01(\x05\"D\n\x10ProbabilityEntry\x12\x1b\n\x05label\x18\x01 \x01(\x0e\x32\x0c.GestureType\x12\x13\n\x0bprobability\x18\x02 \x01(\x02\"\x9b\x03\n\x06Update\x12\"\n\x0csensorFrames\x18\x01 \x03(\x0b\x32\x0c.SensorFrame\x12\x1a\n\x08gestures\x18\x02 \x03(\x0b\x32\x08.Gesture\x12 \n\x0btouchEvents\x18\x03 \x03(\x0b\x32\x0b.TouchEvent\x12\"\n\x0c\x62uttonEvents\x18\x04 \x03(\x0b\x32\x0c.ButtonEvent\x12\"\n\x0crotaryEvents\x18\x05 \x03(\x0b\x32\x0c.RotaryEvent\x12\x1f\n\x07signals\x18\x06 \x03(\x0e\x32\x0e.Update.Signal\x12\x11\n\tdeltaTime\x18\x07 \x01(\x05\x12\x10\n\x08unixTime\x18\x08 \x01(\x03\x12\x13\n\x04info\x18\t \x01(\x0b\x32\x05.Info\x12(\n\rprobabilities\x18\n \x03(\x0b\x32\x11.ProbabilityEntry\x12\x10\n\x08pressure\x18\x10 \x01(\x02\"P\n\x06Signal\x12\x08\n\x04NONE\x10\x00\x12\x0e\n\nDISCONNECT\x10\x01\x12\x14\n\x10\x43ONNECT_APPROVED\x10\x02\x12\x16\n\x12\x44\x45SCRIPTION_UPDATE\x10\x03\x42\r\xaa\x02\nPsix.Protob\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'watch_output_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  _globals['DESCRIPTOR']._options = None
  _globals['DESCRIPTOR']._serialized_options = b'\252\002\nPsix.Proto'
  _globals['_INFO']._serialized_start=37
  _globals['_INFO']._serialized_end=205
  _globals['_INFO_HAND']._serialized_start=168
  _globals['_INFO_HAND']._serialized_end=205
  _globals['_SENSORFRAME']._serialized_start=208
  _globals['_SENSORFRAME']._serialized_end=366
  _globals['_GESTURE']._serialized_start=368
  _globals['_GESTURE']._serialized_end=424
  _globals['_TOUCHEVENT']._serialized_start=427
  _globals['_TOUCHEVENT']._serialized_end=639
  _globals['_TOUCHEVENT_TOUCHEVENTTYPE']._serialized_start=571
  _globals['_TOUCHEVENT_TOUCHEVENTTYPE']._serialized_end=639
  _globals['_ROTARYEVENT']._serialized_start=641
  _globals['_ROTARYEVENT']._serialized_end=687
  _globals['_BUTTONEVENT']._serialized_start=689
  _globals['_BUTTONEVENT']._serialized_end=733
  _globals['_PROBABILITYENTRY']._serialized_start=735
  _globals['_PROBABILITYENTRY']._serialized_end=803
  _globals['_UPDATE']._serialized_start=806
  _globals['_UPDATE']._serialized_end=1217
  _globals['_UPDATE_SIGNAL']._serialized_start=1137
  _globals['_UPDATE_SIGNAL']._serialized_end=1217
# @@protoc_insertion_point(module_scope)
