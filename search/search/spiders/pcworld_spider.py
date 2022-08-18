from search.spiders.currysspider import CurrysSpider

# pcworld.co.uk seems to have the same page structure as currys.co.uk,
# they can be handled the same
class PcworldSpider(CurrysSpider):

    name = "pcworld"

    def init_sub(self):
        super(PcworldSpider, self).init_sub()
        self.target_site = "pcworld"
        self.domain = "http://www.pcworld.co.uk"
