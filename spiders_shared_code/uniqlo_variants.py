import lxml.html


class UniqloVariants(object):

    def setupSC(self, response, product_json):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)
        self.product_json = product_json

    def setupCH(self, tree_html, product_json):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_json = product_json

    def _variants(self):
        try:
            color_info_list = self.product_json["color_info_list"]
            size_info_list = self.product_json["size_info_list"]
            length_info_list = self.product_json["length_info_list"]

            color_key_value = {}

            for color_info in color_info_list:
                color_key_value[color_info["color_cd"]] = color_info["color_nm"]

            size_key_value = {}

            for size_info in size_info_list:
                size_key_value[size_info["size_cd"]] = size_info["size_nm"]

            length_key_value = {}

            for length_info in length_info_list:
                length_key_value[length_info["length_cd"]] = length_info["length_nm"]

            variants = self.product_json["l2_goods_list"]
            variant_list = []

            for index, variant in enumerate(variants):
                if int(variant["real_stock_cnt"]) > 0:
                    in_stock = True
                else:
                    in_stock = False

                price = variant["sales_price"]

                selected = False

                url = None

                properties = {}

                if color_key_value[variant["color_cd"]]:
                    properties["color"] = color_key_value[variant["color_cd"]]

                if size_key_value[variant["size_cd"]]:
                    properties["size"] = size_key_value[variant["size_cd"]]

                if length_key_value[variant["length_cd"]]:
                    properties["length"] = length_key_value[variant["length_cd"]]

                variant_list.append({"in_stock": in_stock, "price": price, "properties": properties, "selected": selected, "url": url})

            if not variant_list:
                return None

            return variant_list
        except:
            return None
