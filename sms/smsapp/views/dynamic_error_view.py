from django.shortcuts import render

def dynamic_error_view(request):
    code = request.GET.get('code', '500')
    code = str(code)
    messages = {
        '400': 'Bad Request – Client sent a malformed request.',
        '401': 'Unauthorized – Authentication is required.',
        '403': 'Forbidden – Access is denied.',
        '404': 'Not Found – The requested page was not found.',
        '405': 'Method Not Allowed – That HTTP method is not supported.',
        '408': 'Request Timeout – The server timed out waiting for the request.',
        '500': 'Internal Server Error – Something broke on our end.',
        '502': 'Bad Gateway – Invalid response from upstream server.',
        '503': 'Service Unavailable – Server is overloaded or under maintenance.',
        '504': 'Gateway Timeout – Server did not get a response in time.',
    }
    return render(request, 'dynamic_error.html', {
        'code': code,
        'message': messages.get(code, 'Unknown error occurred.')
    })
