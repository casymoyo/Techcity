from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa


def generate_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    response = HttpResponse(content_type="application/pdf")
    # response['Content-Disposition'] = f'attachment; filename="{'report'}"'
    pdf_status = pisa.CreatePDF(html, dest=response)
    if pdf_status.err:
        return HttpResponse("Some errors were encountered <pre>" + html + "</pre>")

    return response

