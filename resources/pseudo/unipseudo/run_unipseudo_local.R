#!/usr/bin/env Rscript
# Headless (no web UI) run of the UniPseudo generation algorithm for Polish.
#
# Uses the UNMODIFIED UniPseudo sources from the local sparse clone of
# https://github.com/chrplr/openlexicon (apps/unipseudo/www/...):
#   - www/data/uiElements.R            (constants: "bigram"/"trigram", "No constraint", html markers)
#   - www/data/loadingDatasets.R       (only the `latin_languages`/`non_latin_languages` vectors are evaluated)
#   - www/functions/filterFunctions.R  (checkConsonants / checkSameLetter / checkDiacritic + filtersList presets)
#   - www/functions/generatePseudo.R   (generate_pseudowords(): the Markov chain on positional bi/trigrams)
#
# The only adaptations, done in memory at load time (files on disk are untouched):
#   * `shinyjs::html(...)` progress messages are redirected to a no-op (no Shiny session here),
#   * `shinyalert(...)` pop-ups are replaced by message().
#
# Word source and settings replicate what app.R does for language "Polish":
#   * models  = WorldLex-Polish words with nbcar == len and BlogFreqPm > 0.5   (get_dataset_words default case)
#   * exclude = all WorldLex-Polish words with nbcar == len                    (get_dataset_words need_full_list=TRUE)
#   * algorithm: bigram for len 3-5, trigram for len >= 6                      (observeEvent(input$longueur) in app.R)
#   * constraint presets for a "latin" language: max 3 consecutive consonants, max 2 identical consecutive letters,
#     no diacritic limit                                                       (filtersList presets in filterFunctions.R)
# Not replicated: app.R passes the table through fix.encoding() (rvest::html_encoding_guess + iconv); here the RDS
# is used as is (its Word column is UTF-8; nbcar already counts characters).
#
# Usage:
#   Rscript run_unipseudo_local.R [n=20] [len=6] [seed=1] [out.csv] [models.txt]
#     models.txt (optional): own UTF-8 word list, one word per line, used instead of the WorldLex selection
#                            (words of other lengths are dropped, as in the app).

args <- commandArgs(trailingOnly = TRUE)
n    <- if (length(args) >= 1) as.integer(args[1]) else 20L
len  <- if (length(args) >= 2) as.integer(args[2]) else 6L
seed <- if (length(args) >= 3) as.integer(args[3]) else 1L
out  <- if (length(args) >= 4) args[4] else NA_character_
models_file <- if (length(args) >= 5) args[5] else NA_character_

script_path <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[1])
here <- normalizePath(dirname(script_path))
app  <- file.path(here, "openlexicon", "apps", "unipseudo", "www")
rds  <- file.path(here, "data", "WorldLex-Polish.rds")

suppressPackageStartupMessages(library(shiny))  # only for `tags` used by the constants in uiElements.R

# 1. constants
source(file.path(app, "data", "uiElements.R"), encoding = "UTF-8")

# 2. only the language vectors from loadingDatasets.R (the rest of that file needs rjson and all 64 json files)
for (e in parse(file.path(app, "data", "loadingDatasets.R"), encoding = "UTF-8")) {
  if (is.call(e) && identical(e[[1]], as.name("=")) || is.call(e) && identical(e[[1]], as.name("<-"))) {
    if (as.character(e[[2]])[1] %in% c("latin_languages", "non_latin_languages")) eval(e, globalenv())
  }
}
stopifnot("Polish" %in% latin_languages)

# 3. filters (unmodified)
source(file.path(app, "functions", "filterFunctions.R"), encoding = "UTF-8")

# 4. generator, with UI side effects neutralised
shinyalert <- function(title = "", text = "", ...) message("[shinyalert] ", title, ": ", text)
.noop_html <- function(...) invisible(NULL)
src <- readLines(file.path(app, "functions", "generatePseudo.R"), encoding = "UTF-8")
src <- gsub("shinyjs::html", ".noop_html", src, fixed = TRUE)
eval(parse(text = src, encoding = "UTF-8"), globalenv())

# 5. data: same selection rules as get_dataset_words() for a WorldLex dataset
language <- "Polish"
wl <- as.data.frame(readRDS(rds))
exclude <- wl$Word[wl$nbcar == len]
if (is.na(models_file)) {
  words <- wl$Word[wl$BlogFreqPm > 0.5 & wl$nbcar == len]
} else {
  words <- readLines(models_file, encoding = "UTF-8")
}
# same normalisation as the eventReactive(input$go) block in app.R
wordsok <- words[nchar(words) == len]
wordsok <- tolower(wordsok)
wordsok <- wordsok[!duplicated(wordsok)]
wordsok <- as.character(wordsok)

# 6. presets, as set by observeEvent(input$language) in app.R
# Set environment variable UNIPSEUDO_CONSTRAINTS=none to switch all constraints off (the live web app at
# https://www.lexique.org/django/unipseudo/ reported no presets for Polish on 2026-11-13).
use_presets <- Sys.getenv("UNIPSEUDO_CONSTRAINTS", "presets") != "none"
input <- list()
for (f in filtersList) {
  input[[f[["name"]]]] <- if (use_presets && language %in% f[["preset"]][["languages"]]) as.character(f[["preset"]][["value"]]) else default_filter_option
}
algo <- if (len <= 5) big_choice else trig_choice

cat(sprintf("UniPseudo local run: language=%s len=%d n=%d algorithm=%s seed=%d\n", language, len, n, algo, seed))
cat(sprintf("models (source words): %d ; exclusion list: %d ; constraints: %s\n", length(wordsok), length(exclude),
            paste(names(input), unlist(input), sep = "=", collapse = ", ")))

set.seed(seed)
res <- generate_pseudowords(n = n, len = len, models = wordsok, len_grams = algo, language = language,
                            input = input, exclude = exclude)

# strip the html colouring exactly as the app's download handler does
strip <- function(x) { for (m in c(font_first_element, font_second_element, font_previous_letters, font_fade, font_fade_end)) x <- gsub(m, "", x, fixed = TRUE); x }
res[] <- lapply(res, strip)
cat(sprintf("generated: %d\n", nrow(res)))
print(res, row.names = FALSE)
if (!is.na(out)) {
  write.csv(res, out, row.names = FALSE, fileEncoding = "UTF-8")
  cat("wrote", out, "\n")
}
