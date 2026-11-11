"""Export CSV sans injection de formules : une cellule qui commence par = + - @ serait exécutée par Excel."""
import csv

from django.http import HttpResponse

DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(DANGEROUS) else text


def csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # BOM : Excel lit correctement les accents
    writer = csv.writer(response, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(c) for c in row])
    return response
