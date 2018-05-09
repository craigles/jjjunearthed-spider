import scrapy
import datetime
from JJJUnearthed import XPath
from JJJUnearthed import items


class JJJUnearthedSpider(scrapy.Spider):
    name = "JJJUnearthedSpider"
    spider_modules = ["JJJUnearthed.spiders"]

    def __init__(self, from_index=0, to_index=103607, download_delay=5, *args, **kwargs):
        super(JJJUnearthedSpider, self).__init__(*args, **kwargs)
        self.download_delay = download_delay
        self.start_urls = [
            "https://www.triplejunearthed.com/node?page=%d" % index for index in range(int(from_index), int(to_index))
        ]

    def parse(self, response):
        artist_links = response.xpath(
            "//a[starts-with(@href, '/artist/') "
            "and not(contains(@href, 'track/')) "
            "and not(substring(@href, string-length(@href) - string-length('/track') +1) = '/track') "
            "and not(contains(@href, 'review/'))][1]/@href").extract()

        self.logger.info("Parsing page")

        for artist_link in artist_links:
            yield scrapy.Request("https://www.triplejunearthed.com" + artist_link, callback=self.get_artist)

    @staticmethod
    def to_rating(rating):
        return {
            "0": 0,
            "5": 0.5,
            "10": 1,
            "15": 1.5,
            "20": 2,
            "25": 2.5,
            "30": 3,
            "35": 3.5,
            "40": 4,
            "45": 4.5,
            "50": 5,
        }[rating]

    @staticmethod
    def get_artist_likes(response):
        like_urls = response.xpath(
            "//div[@class='content_module module_artistinfo'][1]/div/p/a[contains(@href, '/artist/')]/@href").extract()
        like_names = response.xpath(
            "//div[@class='content_module module_artistinfo'][1]/div/p/a[contains(@href, '/artist/')]/text()").extract()

        for i, like_url in enumerate(like_urls):
            yield items.ArtistRef(
                url="https://www.triplejunearthed.com" + like_url,
                name=like_names[i].strip()
            )

    def get_artist(self, response):
        name = response.css("h1#unearthed-profile-title ::text").extract_first()
        location = response.css("span.genres.location span.location ::text").extract_first()
        genre = response.css("span.genres.location span.genre ::text").extract()
        website = response.xpath("//h3[.='Website'][1]/following-sibling::p[1]/a/text()").extract()
        social_links = response.xpath("//ul[@class ='social']/li/a/@href").extract()
        tags = response.xpath("//h3[.='Tags'][1]/following-sibling::p/a/text()").extract()
        members = response.xpath("//h3[.='band members'][1]/following-sibling::p/text()").extract_first()
        influences = response.xpath("//h3[.='Influences'][1]/following-sibling::p/text()").extract_first()

        self.logger.info("Parsing artist")

        return items.Artist(
            name=name.strip(),
            location=location,
            genre=genre,
            members="" if members is None else members.strip(),
            links=website + social_links,
            tags=tags,
            influences="" if influences is None else influences.strip(),
            url=response.url,
            tracks=self.get_tracks(response),
            likes=list(self.get_artist_likes(response))
        )

    @staticmethod
    def played_on_jjj(response, name):
        played = response.xpath(
            "//div[@class='track_name' and .=" + XPath.to_literal(name) +
            "][1]/following-sibling::div/div[@class='icons playedontriplej'][1]").extract_first()

        return played is not None

    @staticmethod
    def played_on_unearthed(response, name):
        played = response.xpath(
            "//div[@class='track_name' and .=" + XPath.to_literal(name) +
            "][1]/following-sibling::div/div[@class='icons unearthed'][1]").extract_first()

        return played is not None

    @staticmethod
    def mature(response, name):
        played = response.xpath(
            "//div[@class='track_name' and .=" + XPath.to_literal(name) +
            "][1]/following-sibling::div/div[@class='icons mature'][1]").extract_first()

        return played is not None

    @staticmethod
    def to_date(date, input_format):
        return datetime.datetime.strptime(date, input_format).strftime("%Y-%m-%d")

    def get_tracks(self, response):
        track_names = response.css("div.track_name ::text").extract()
        track_plays = response.xpath("//p[@class='plays'][1]/following-sibling::p")
        track_downloads = response.xpath("//p[@class='downloads'][1]/following-sibling::p")
        track_loves = response.xpath("//p[@class='loves'][1]/following-sibling::p")
        track_shares = response.xpath("//p[@class='shares'][1]/following-sibling::p")
        track_links = response.xpath("//a[@class='download'][1]/@href").extract()
        track_dates = response.css("div.date_uploaded ::text").extract()
        track_avg_rating = response.css("p.stars_sm ::text").extract()
        number_of_reviews = response.xpath("//p[@class='reviews'][1]/following-sibling::p")

        tracks = [items.Track(
            name=name,
            plays=0 if track_plays[i].xpath("text()").extract_first() is None else int(track_plays[i].xpath("text()").extract_first()),
            downloads=0 if track_downloads[i].xpath("text()").extract_first() is None else int(track_downloads[i].xpath("text()").extract_first()),
            loves=0 if track_loves[i].xpath("text()").extract_first() is None else int(track_loves[i].xpath("text()").extract_first()),
            number_of_reviews=0 if number_of_reviews[i].xpath("text()").extract_first() is None else int(number_of_reviews[i].xpath("text()").extract_first()),
            link="https://www.triplejunearthed.com" + track_links[i],
            played_on_jjj=self.played_on_jjj(response, name),
            played_on_unearthed=self.played_on_unearthed(response, name),
            mature=self.mature(response, name),
            avg_rating=self.to_rating(track_avg_rating[i].strip()),
            date=self.to_date(track_dates[i].replace("Uploaded ", ""), "%d %b %y"),
            shares=0 if track_shares[i].xpath("text()").extract_first() is None else int(track_shares[i].xpath("text()").extract_first())) for i, name in enumerate(track_names)]

        for track in tracks:
            track["reviews"] = list(self.get_reviews(response, track["name"]))

        return tracks

    def get_reviews(self, response, track_name):
        review_tracks = response.css("h4.track ::text").extract()
        review_reviewers = response.css("a.reviewer_name ::text").extract()
        review_dates = response.css("p.review_date ::text").extract()
        review_ratings = response.css("div.stars ::text").extract()

        for i, review_track in enumerate(review_tracks):
            if review_track.strip() == track_name.strip():
                yield items.Review(
                    reviewer=review_reviewers[i].strip(),
                    date=self.to_date(review_dates[i].strip(), "%d %b %Y"),
                    rating=self.to_rating(review_ratings[i].strip()))
