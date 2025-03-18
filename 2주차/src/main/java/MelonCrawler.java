package main.java;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import java.io.FileWriter;
import java.io.IOException;
import java.util.Arrays;
import java.util.List;

public class MelonCrawler {
    private static final String FILE_PATH = "music_data.csv";

    public static void main(String[] args) {
        try {
            FileWriter writer = new FileWriter(FILE_PATH);
            writer.append("곡명,아티스트,장르,발매연도,앨범\n");

            // 1. 실시간 차트 크롤링
            crawlMelonChart("https://www.melon.com/chart/index.htm", writer);

            // 2. 장르별 차트 크롤링 (예: 발라드, 힙합, R&B)
            List<String> genreUrls = Arrays.asList(
                    "https://www.melon.com/genre/song_list.htm?gnrCode=GN0100", // 발라드
                    "https://www.melon.com/genre/song_list.htm?gnrCode=GN0300", // 힙합
                    "https://www.melon.com/genre/song_list.htm?gnrCode=GN0500"  // R&B
            );
            for (String url : genreUrls) {
                crawlMelonChart(url, writer);
            }

            // 3. 최신 음악 크롤링
            crawlMelonChart("https://www.melon.com/new/index.htm", writer);

            // 4. 인기 플레이리스트 크롤링
            crawlMelonChart("https://www.melon.com/dj/today/djtoday_list.htm", writer);

            writer.flush();
            writer.close();
            System.out.println("✅ 다양한 음악 데이터 크롤링 완료!");

        } catch (IOException e) {
            System.out.println("❌ 크롤링 오류 발생: " + e.getMessage());
        }
    }

    private static void crawlMelonChart(String url, FileWriter writer) {
        try {
            Document doc = Jsoup.connect(url).get();
            Elements songElements = doc.select("tr.lst50, tr.lst100");

            for (Element songElement : songElements) {
                String title = songElement.select(".rank01 a").text();
                String artist = songElement.select(".rank02 a").text();
                String album = songElement.select(".rank03 a").text();
                String releaseYear = "Unknown";  // 발매연도 추가 가능
                String genre = "Unknown";  // 장르 추가 가능

                writer.append(title).append(",")
                        .append(artist).append(",")
                        .append(genre).append(",")
                        .append(releaseYear).append(",")
                        .append(album).append("\n");
            }

        } catch (IOException e) {
            System.out.println("❌ " + url + " 크롤링 실패: " + e.getMessage());
        }
    }
}
