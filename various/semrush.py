import argparse
import re
import requests


def get_seo_url(url):
    product_id = re.search(r'samsclub\.com/sams/(?:.*/)?((?:prod)?\d+)\.ip', url)

    if product_id:
        redirect_url = 'https://www.samsclub.com/sams/shop/product.jsp?productId={}'.format(product_id.group(1))

        try:
            response = requests.get(redirect_url, timeout=60, allow_redirects=False)
        except:
            pass
        else:
            seo_url = response.headers.get('location')

            if seo_url:
                return seo_url.split('?')[0]

    return url


def url_organic(args, try_other_url=True):
    endpoint = 'https://api.semrush.com/'

    params = {
        'type': 'url_organic',
        'key': args.key,
        'url': args.url,
        'database': args.database,
        'display_limit': args.display_limit,
        'export_columns': args.export_columns
    }

    try:
        response = requests.get(endpoint, params=params)
    except Exception as e:
        return e
    else:
        if 'ERROR 50' in response.content and try_other_url:
            args.url = get_seo_url(args.url)
            return url_organic(args, False)

        return response.content


def backlinks_overview(args, try_other_url=True):
    endpoint = 'https://api.semrush.com/analytics/v1/'

    params = {
        'type': 'backlinks_overview',
        'key': args.key,
        'target': args.target,
        'target_type': args.target_type,
        'export_columns': args.export_columns
    }

    try:
        response = requests.get(endpoint, params=params)
    except Exception as e:
        return e
    else:
        if 'ERROR 50' in response.content and try_other_url:
            if args.target_type == 'url':
                args.target = get_seo_url(args.target)
                return backlinks_overview(args, False)

        return response.content


def get_args():
    parser = argparse.ArgumentParser(description='SEMrush API. Script to call SEMrush API '
                                                 'https://www.semrush.com/api-documentation/')

    parser.add_argument('--key',
                        default='e333e9506cd32ad922850a653179898e',
                        help='An identification key assigned to a user after subscribing to SEMrush '
                             'that is available via Profile page.')

    subparsers = parser.add_subparsers(help='A type of report')

    parser_url_organic = subparsers.add_parser(
        'url_organic',
        help="This report lists keywords that bring users to a URL via Google's top 20 organic search results.")
    parser_url_organic.set_defaults(func=url_organic)

    parser_url_organic.add_argument('url',
                                    help="The URL of a landing page you'd like to investigate.")

    parser_url_organic.add_argument('--database',
                                    default='us',
                                    help='A regional database (one value from the list).')

    parser_url_organic.add_argument('--display_limit',
                                    type=int,
                                    default=200,
                                    help='The number of results returned to a request; if this parameter is not '
                                         'specified or equal to 0, the default value will be 10,000 lines.')

    parser_url_organic.add_argument('--export_columns',
                                    default='Ph,Po,Nq,Cp,Co,Tr,Tc',
                                    help='Required columns must be separated by commas; if this parameter is '
                                         'not specified, default columns will be sent.')

    parser_backlinks_overview = subparsers.add_parser(
        'backlinks_overview',
        help='This report provides a summary of backlinks, including their type, referring domains and '
             'IP addresses for a domain, root domain, or URL.')
    parser_backlinks_overview.set_defaults(func=backlinks_overview)

    parser_backlinks_overview.add_argument('target',
                                           help='A root domain, domain or URL address.')

    parser_backlinks_overview.add_argument('--target_type',
                                           default='url',
                                           help='A type of requested target')

    parser_backlinks_overview.add_argument('--export_columns',
                                           default='total',
                                           help='Required columns must be separated by commas; if this parameter '
                                                'is not specified, default columns will be sent.')

    return parser.parse_args()


if __name__ == '__main__':
    args = get_args()

    print args.func(args)
