# Eksport listy słów WorldLex-Polish (wszystkie długości 3–15) do TSV dla portu UniPseudo w Pythonie.
# Uruchomienie (w tym katalogu):  Rscript export_worldlex.R
# Wynik: data/worldlex_polish_words.tsv  (kolumny: word, nbcar, BlogFreqPm; kodowanie UTF-8)
wl <- as.data.frame(readRDS("data/WorldLex-Polish.rds"))
wl <- wl[!is.na(wl$nbcar) & wl$nbcar >= 3 & wl$nbcar <= 15, c("Word", "nbcar", "BlogFreqPm")]
names(wl)[1] <- "word"
wl$word <- enc2utf8(as.character(wl$word))
con <- file("data/worldlex_polish_words.tsv", open = "wb")
writeLines(enc2utf8(paste(c("word", wl$word), c("nbcar", wl$nbcar), c("BlogFreqPm", wl$BlogFreqPm), sep = "\t")), con, useBytes = TRUE)
close(con)
cat(nrow(wl), "rows written\n")
