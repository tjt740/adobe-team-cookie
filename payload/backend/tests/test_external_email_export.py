from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from app.models.external_member import ExternalMember
from app.services.email_export import XLSX_MEDIA_TYPE


def test_export_selected_emails_as_excel(client, db):
    members = [
        ExternalMember(email="selected@ex.com", login_status="login_failed",
                       mail_password="secret-mail-password", refresh_token="secret-refresh-token",
                       adobe_password="secret-adobe-password", cookie="secret-cookie"),
        ExternalMember(email="unselected@ex.com"),
        ExternalMember(email="=formula&中文@ex.com", login_status="never"),
    ]
    db.add_all(members)
    db.commit()
    response = client.post("/api/external/members/export-emails",
                           json={"ids": [members[2].id, members[0].id, members[2].id]})
    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX_MEDIA_TYPE
    assert response.headers["content-disposition"] == 'attachment; filename="external-emails.xlsx"'
    assert response.headers["cache-control"] == "no-store"
    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        xml = archive.read("xl/worksheets/sheet1.xml")
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        sheet = ET.fromstring(xml)
        cells = sheet.findall("s:sheetData/s:row/s:c", ns)
        assert [cell.attrib["r"] for cell in cells] == ["A1", "A2", "A3"]
        assert all(cell.attrib["t"] == "inlineStr" for cell in cells)
        assert [cell.find("s:is/s:t", ns).text for cell in cells] == [
            "邮箱", "=formula&中文@ex.com", "selected@ex.com",
        ]
        assert not sheet.findall(".//s:f", ns)
        contents = b"".join(archive.read(name) for name in archive.namelist())
        assert b"secret-" not in contents and b"unselected@ex.com" not in contents


@pytest.mark.parametrize("ids, status", [([], 400), ([999999], 404)])
def test_email_export_rejects_empty_or_missing_selection(client, ids, status):
    response = client.post("/api/external/members/export-emails", json={"ids": ids})
    assert response.status_code == status
    assert "application/json" in response.headers["content-type"]


def test_email_export_does_not_silently_drop_deleted_selection(client, db):
    member = ExternalMember(email="exists@ex.com")
    db.add(member)
    db.commit()
    response = client.post("/api/external/members/export-emails",
                           json={"ids": [member.id, 999999]})
    assert response.status_code == 404
    assert "重新勾选" in response.json()["detail"]


def test_email_export_requires_authentication(client):
    from app.api.deps import get_current_user
    from app.main import app

    override = app.dependency_overrides.pop(get_current_user)
    try:
        response = client.post("/api/external/members/export-emails", json={"ids": [1]})
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = override
