from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ReportEntry(_message.Message):
    __slots__ = ("report_id", "locomotive_id", "report_type", "format", "status", "created_at", "data")
    REPORT_ID_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    REPORT_TYPE_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    report_id: str
    locomotive_id: str
    report_type: str
    format: str
    status: str
    created_at: str
    data: bytes
    def __init__(self, report_id: _Optional[str] = ..., locomotive_id: _Optional[str] = ..., report_type: _Optional[str] = ..., format: _Optional[str] = ..., status: _Optional[str] = ..., created_at: _Optional[str] = ..., data: _Optional[bytes] = ...) -> None: ...

class GetReportRequest(_message.Message):
    __slots__ = ("report_id",)
    REPORT_ID_FIELD_NUMBER: _ClassVar[int]
    report_id: str
    def __init__(self, report_id: _Optional[str] = ...) -> None: ...

class GetReportResponse(_message.Message):
    __slots__ = ("report",)
    REPORT_FIELD_NUMBER: _ClassVar[int]
    report: ReportEntry
    def __init__(self, report: _Optional[_Union[ReportEntry, _Mapping]] = ...) -> None: ...

class ListReportsRequest(_message.Message):
    __slots__ = ("locomotive_id", "status", "offset", "limit")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    status: str
    offset: int
    limit: int
    def __init__(self, locomotive_id: _Optional[str] = ..., status: _Optional[str] = ..., offset: _Optional[int] = ..., limit: _Optional[int] = ...) -> None: ...

class ListReportsResponse(_message.Message):
    __slots__ = ("reports", "total")
    REPORTS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    reports: _containers.RepeatedCompositeFieldContainer[ReportEntry]
    total: int
    def __init__(self, reports: _Optional[_Iterable[_Union[ReportEntry, _Mapping]]] = ..., total: _Optional[int] = ...) -> None: ...

class DownloadReportRequest(_message.Message):
    __slots__ = ("report_id",)
    REPORT_ID_FIELD_NUMBER: _ClassVar[int]
    report_id: str
    def __init__(self, report_id: _Optional[str] = ...) -> None: ...

class DownloadReportResponse(_message.Message):
    __slots__ = ("format", "content", "filename", "content_type")
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    CONTENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    format: str
    content: bytes
    filename: str
    content_type: str
    def __init__(self, format: _Optional[str] = ..., content: _Optional[bytes] = ..., filename: _Optional[str] = ..., content_type: _Optional[str] = ...) -> None: ...
