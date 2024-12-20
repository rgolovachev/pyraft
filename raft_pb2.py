# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: raft.proto
# Protobuf Python Version: 5.28.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    28,
    1,
    '',
    'raft.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\nraft.proto\"`\n\x0bVoteRequest\x12\x0c\n\x04term\x18\x01 \x01(\x03\x12\x14\n\x0c\x63\x61ndidate_id\x18\x02 \x01(\x03\x12\x16\n\x0elast_log_index\x18\x03 \x01(\x03\x12\x15\n\rlast_log_term\x18\x04 \x01(\x03\"\x8f\x01\n\rAppendRequest\x12\x0c\n\x04term\x18\x01 \x01(\x03\x12\x11\n\tleader_id\x18\x02 \x01(\x03\x12\x16\n\x0eprev_log_index\x18\x03 \x01(\x03\x12\x15\n\rprev_log_term\x18\x04 \x01(\x03\x12\x17\n\x07\x65ntries\x18\x05 \x03(\x0b\x32\x06.Entry\x12\x15\n\rleader_commit\x18\x06 \x01(\x03\"4\n\x0eGetLeaderReply\x12\x11\n\tleader_id\x18\x01 \x01(\x03\x12\x0f\n\x07\x61\x64\x64ress\x18\x02 \x01(\t\" \n\x0eSuspendRequest\x12\x0e\n\x06period\x18\x01 \x01(\x03\"O\n\nSetRequest\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\x12\x11\n\tis_delete\x18\x03 \x01(\x08\x12\x12\n\nrequest_id\x18\x04 \x01(\t\"\x1b\n\x08SetReply\x12\x0f\n\x07success\x18\x01 \x01(\x08\"`\n\nGetRequest\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\x13\n\x0bneed_master\x18\x02 \x01(\x08\x12\x14\n\x0clast_applied\x18\x03 \x01(\x03\x12\x1a\n\x12last_applied_valid\x18\x04 \x01(\x08\"g\n\x08GetReply\x12\x1f\n\x06status\x18\x01 \x01(\x0e\x32\x0f.GetReplyStatus\x12\r\n\x05value\x18\x02 \x01(\t\x12\x15\n\rredirect_addr\x18\x03 \x01(\t\x12\x14\n\x0clast_applied\x18\x04 \x01(\x03\"P\n\nCasRequest\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\x10\n\x08\x65xpected\x18\x02 \x01(\t\x12\x0f\n\x07\x64\x65sired\x18\x03 \x01(\t\x12\x12\n\nrequest_id\x18\x04 \x01(\t\"?\n\x08\x43\x61sReply\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07\x61pplied\x18\x02 \x01(\x08\x12\x11\n\told_value\x18\x03 \x01(\t\"d\n\x05\x45ntry\x12\x0c\n\x04term\x18\x01 \x01(\x03\x12\x0b\n\x03key\x18\x02 \x01(\t\x12\r\n\x05value\x18\x03 \x01(\t\x12\x0c\n\x04\x63ond\x18\x04 \x01(\t\x12\x10\n\x08has_cond\x18\x05 \x01(\x08\x12\x11\n\tis_delete\x18\x06 \x01(\x08\".\n\x0eResultWithTerm\x12\x0c\n\x04term\x18\x01 \x01(\x03\x12\x0e\n\x06result\x18\x02 \x01(\x08\"\x0e\n\x0c\x45mptyMessage*7\n\x0eGetReplyStatus\x12\n\n\x06\x46\x41ILED\x10\x00\x12\x0b\n\x07SUCCESS\x10\x01\x12\x0c\n\x08REDIRECT\x10\x02\x32\xb6\x02\n\x08RaftNode\x12.\n\x0bRequestVote\x12\x0c.VoteRequest\x1a\x0f.ResultWithTerm\"\x00\x12\x32\n\rAppendEntries\x12\x0e.AppendRequest\x1a\x0f.ResultWithTerm\"\x00\x12-\n\tGetLeader\x12\r.EmptyMessage\x1a\x0f.GetLeaderReply\"\x00\x12+\n\x07Suspend\x12\x0f.SuspendRequest\x1a\r.EmptyMessage\"\x00\x12\"\n\x06SetVal\x12\x0b.SetRequest\x1a\t.SetReply\"\x00\x12\"\n\x06GetVal\x12\x0b.GetRequest\x1a\t.GetReply\"\x00\x12\"\n\x06\x43\x61sVal\x12\x0b.CasRequest\x1a\t.CasReply\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'raft_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_GETREPLYSTATUS']._serialized_start=972
  _globals['_GETREPLYSTATUS']._serialized_end=1027
  _globals['_VOTEREQUEST']._serialized_start=14
  _globals['_VOTEREQUEST']._serialized_end=110
  _globals['_APPENDREQUEST']._serialized_start=113
  _globals['_APPENDREQUEST']._serialized_end=256
  _globals['_GETLEADERREPLY']._serialized_start=258
  _globals['_GETLEADERREPLY']._serialized_end=310
  _globals['_SUSPENDREQUEST']._serialized_start=312
  _globals['_SUSPENDREQUEST']._serialized_end=344
  _globals['_SETREQUEST']._serialized_start=346
  _globals['_SETREQUEST']._serialized_end=425
  _globals['_SETREPLY']._serialized_start=427
  _globals['_SETREPLY']._serialized_end=454
  _globals['_GETREQUEST']._serialized_start=456
  _globals['_GETREQUEST']._serialized_end=552
  _globals['_GETREPLY']._serialized_start=554
  _globals['_GETREPLY']._serialized_end=657
  _globals['_CASREQUEST']._serialized_start=659
  _globals['_CASREQUEST']._serialized_end=739
  _globals['_CASREPLY']._serialized_start=741
  _globals['_CASREPLY']._serialized_end=804
  _globals['_ENTRY']._serialized_start=806
  _globals['_ENTRY']._serialized_end=906
  _globals['_RESULTWITHTERM']._serialized_start=908
  _globals['_RESULTWITHTERM']._serialized_end=954
  _globals['_EMPTYMESSAGE']._serialized_start=956
  _globals['_EMPTYMESSAGE']._serialized_end=970
  _globals['_RAFTNODE']._serialized_start=1030
  _globals['_RAFTNODE']._serialized_end=1340
# @@protoc_insertion_point(module_scope)
