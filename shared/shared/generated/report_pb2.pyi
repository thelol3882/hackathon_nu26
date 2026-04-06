from collections.abc import Iterable as _Iterable
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers

DESCRIPTOR: _descriptor.FileDescriptor

class ReportEntry(_message.Message):
    __slots__ = ("created_at", "data", "format", "locomotive_id", "report_id", "report_type", "status")
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
    def __init__(
        self,
        report_id: str | None = ...,
        locomotive_id: str | None = ...,
        report_type: str | None = ...,
        format: str | None = ...,
        status: str | None = ...,
        created_at: str | None = ...,
        data: bytes | None = ...,
    ) -> None: ...

class GetReportRequest(_message.Message):
    __slots__ = ("report_id",)
    REPORT_ID_FIELD_NUMBER: _ClassVar[int]
    report_id: str
    def __init__(self, report_id: str | None = ...) -> None: ...

class GetReportResponse(_message.Message):
    __slots__ = ("report",)
    REPORT_FIELD_NUMBER: _ClassVar[int]
    report: ReportEntry
    def __init__(self, report: ReportEntry | _Mapping | None = ...) -> None: ...

class ListReportsRequest(_message.Message):
    __slots__ = ("limit", "locomotive_id", "offset", "status")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    status: str
    offset: int
    limit: int
    def __init__(
        self,
        locomotive_id: str | None = ...,
        status: str | None = ...,
        offset: int | None = ...,
        limit: int | None = ...,
    ) -> None: ...

class ListReportsResponse(_message.Message):
    __slots__ = ("reports", "total")
    REPORTS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    reports: _containers.RepeatedCompositeFieldContainer[ReportEntry]
    total: int
    def __init__(self, reports: _Iterable[ReportEntry | _Mapping] | None = ..., total: int | None = ...) -> None: ...

class DownloadReportRequest(_message.Message):
    __slots__ = ("report_id",)
    REPORT_ID_FIELD_NUMBER: _ClassVar[int]
    report_id: str
    def __init__(self, report_id: str | None = ...) -> None: ...

class DownloadReportResponse(_message.Message):
    __slots__ = ("content", "content_type", "filename", "format")
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    CONTENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    format: str
    content: bytes
    filename: str
    content_type: str
    def __init__(
        self,
        format: str | None = ...,
        content: bytes | None = ...,
        filename: str | None = ...,
        content_type: str | None = ...,
    ) -> None: ...
