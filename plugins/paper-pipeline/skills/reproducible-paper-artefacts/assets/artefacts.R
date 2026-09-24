## artefacts.R -- emit artefacts from R. Source this first in every script.
##
##     source("R/lib/artefacts.R")
##
##     fit <- estimate(data)
##     emit_numbers(
##         snakemake@output[["numbers"]],
##         primaryAte = num(fit$estimate, 2),
##         primarySe  = num(fit$se, 3),
##         primaryCi  = ci(fit$lo, fit$hi, 2),
##         primaryN   = int(fit$n)
##     )
##
## Rounding happens once, here. Numbers in a paper go inconsistent when each
## use site rounds by hand, and they stay consistent when the digit count is an
## argument to one function.
##
## Every write is checked before it happens, by tools/record_provenance.py: the
## tier's branch rule, a clean code tree, and macro names LaTeX will accept. A
## refused write leaves nothing on disk. The same script records provenance
## afterwards, for this file and for artefacts.py, so the two languages cannot
## drift apart on "what commit built this".
##
## A note on the read tracking below, because overselling it would be worse
## than not having it. Sourcing this file installs a wrapper over source() and
## sys.source() that records what they load. That wrapper sees source() and
## nothing else. It does not see library() of a local package, box::use(),
## Rcpp::sourceCpp(), or any data file opened directly. Wrapping data reads in
## track_read() covers the important half of what is missing. What remains is
## a lint that catches the common case, not a proof, and the tooling says so
## wherever it reports on it.

.artefact_root <- local({
    dir <- normalizePath(getwd(), mustWork = TRUE)
    repeat {
        if (file.exists(file.path(dir, ".artefacts.toml"))) break
        parent <- dirname(dir)
        if (identical(parent, dir)) {
            stop("No .artefacts.toml found above ", getwd(),
                 ". artefacts.R only works inside a reproducible-paper-artefacts ",
                 "project.", call. = FALSE)
        }
        dir <- parent
    }
    dir
})

.artefact_reads <- new.env(parent = emptyenv())

## Rscript inherits a different PATH from an interactive shell, so a bare
## "python3" here can resolve to the system interpreter (3.9 on macOS) while
## everything else in the project runs on a much newer one. The tooling needs
## 3.11 for tomllib, so the interpreter is resolved once and checked, rather
## than discovered through a confusing failure inside record_provenance.
.artefact_python <- local({
    cached <- NULL
    function() {
        if (!is.null(cached)) return(cached)
        candidates <- c(
            Sys.getenv("ARTEFACTS_PYTHON", unset = NA),
            Sys.which("python3"),
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3.13",
            "/usr/bin/python3"
        )
        candidates <- unique(candidates[!is.na(candidates) & nzchar(candidates)])
        for (cand in candidates) {
            if (!file.exists(cand) && !nzchar(Sys.which(cand))) next
            ok <- suppressWarnings(system2(
                cand, c("-c", shQuote("import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)")),
                stdout = FALSE, stderr = FALSE))
            if (identical(ok, 0L)) {
                cached <<- cand
                return(cand)
            }
        }
        stop("No Python 3.11 or newer found for the artefact tooling. Tried: ",
             paste(candidates, collapse = ", "),
             ". Set ARTEFACTS_PYTHON to the interpreter you want used.",
             call. = FALSE)
    }
})

.artefact_validate <- function(path, macros = NULL) {
    ## Validate before writing: the tier's branch rule, a clean tree, and the
    ## macro names. A bad name discovered after the write leaves a .tex on disk
    ## that breaks the compile for every coauthor.
    macro_file <- tempfile(fileext = ".json")
    on.exit(unlink(macro_file), add = TRUE)
    writeLines(.artefact_json_object(macros), macro_file)
    status <- system2(.artefact_python(), shQuote(c(
        file.path(.artefact_root, "tools", "record_provenance.py"),
        "--validate", "--path", path, "--macros", macro_file)),
        stdout = "", stderr = "")
    if (!identical(status, 0L)) {
        stop("Refusing to write ", path, ": see the message above.", call. = FALSE)
    }
    invisible(TRUE)
}

## ---------------------------------------------------------------------------
## Read tracking
## ---------------------------------------------------------------------------

## Wrap the path of any file you read, so it is recorded as an input:
##     data <- readRDS(track_read("data/analysis.rds"))
## It returns the path, so it drops into any reader rather than covering a short
## list of pre-wrapped ones that will never match what you actually use.
track_read <- function(path) {
    if (is.character(path) && length(path) == 1L && file.exists(path)) {
        full <- normalizePath(path, mustWork = FALSE)
        rel <- sub(paste0("^", gsub("([.|()\\^{}+$*?\\[\\]])", "\\\\\\1",
                                    .artefact_root), "/"), "", full)
        assign(rel, TRUE, envir = .artefact_reads)
    }
    invisible(path)
}

## The wrapper keeps source()'s own `local` argument. With local = TRUE,
## base::source() evaluates in the frame it was called from, which would now be
## the wrapper's frame, and the definitions would vanish when it returns. So
## TRUE is turned into the caller's frame before the call.
local({
    real_source <- base::source
    real_sys_source <- base::sys.source
    assign("source", function(file, local = FALSE, ...) {
        if (!missing(file)) track_read(file)
        if (isTRUE(local)) local <- parent.frame()
        real_source(file, local = local, ...)
    }, envir = globalenv())
    assign("sys.source", function(file, ...) {
        track_read(file)
        real_sys_source(file, ...)
    }, envir = globalenv())
})

## ---------------------------------------------------------------------------
## Formatting. Round once, here.
## ---------------------------------------------------------------------------

num <- function(value, digits = 2) {
    ## formatC rather than round, so 0.40 keeps its trailing zero instead of
    ## appearing as 0.4 next to a 0.42 three sentences later.
    sprintf("\\num{%s}", formatC(value, format = "f", digits = digits))
}

int <- function(value) {
    ## Named int() rather than integer(), because defining integer() here would
    ## mask base::integer() for every script sourced afterwards, and code that
    ## preallocates a vector with integer(n) would silently get a LaTeX string.
    sprintf("\\num{%d}", as.integer(round(value)))
}

ci <- function(lo, hi, digits = 2) {
    sprintf("(\\num{%s}, \\num{%s})",
            formatC(lo, format = "f", digits = digits),
            formatC(hi, format = "f", digits = digits))
}

pct <- function(value, digits = 1) {
    ## Pass 42 for 42 percent, not 0.42.
    sprintf("\\qty{%s}{\\percent}", formatC(value, format = "f", digits = digits))
}

pval <- function(value, digits = 3) {
    floor_value <- 10^(-digits)
    if (value < floor_value) {
        sprintf("\\(<\\)\\num{%s}", formatC(floor_value, format = "f", digits = digits))
    } else {
        sprintf("\\num{%s}", formatC(value, format = "f", digits = digits))
    }
}

## ---------------------------------------------------------------------------
## Methods: text, lists and sets. A macro whose name starts with mth is a
## methods setting, recorded from what ran; `make methods` tracks it.
## ---------------------------------------------------------------------------

.latex_special <- c("\\" = "\\textbackslash{}", "&" = "\\&", "%" = "\\%",
                    "$" = "\\$", "#" = "\\#", "_" = "\\_", "{" = "\\{",
                    "}" = "\\}", "~" = "\\textasciitilde{}",
                    "^" = "\\textasciicircum{}")

latex_text <- function(x) {
    ## Any value as LaTeX text, with the special characters escaped. Learner
    ## and package names are full of underscores, and one unescaped underscore
    ## stops the compile.
    vapply(as.character(x), function(s) {
        chs <- strsplit(s, "", fixed = TRUE)[[1]]
        hit <- chs %in% names(.latex_special)
        chs[hit] <- .latex_special[chs[hit]]
        paste0(chs, collapse = "")
    }, character(1), USE.NAMES = FALSE)
}

words <- function(items, conj = "and", escape = TRUE) {
    ## A list for prose: "a", "a and b", "a, b, and c". Pass readable names.
    x <- as.character(items)
    if (escape) x <- latex_text(x)
    n <- length(x)
    if (n == 0L) stop("words() needs at least one item.", call. = FALSE)
    if (n == 1L) return(x)
    if (n == 2L) return(paste(x[1], conj, x[2]))
    paste0(paste(x[-n], collapse = ", "), ", ", conj, " ", x[n])
}

.plain_number <- function(v, digits = NULL) {
    ## siunitx input: integers whole, others to six significant digits. The
    ## same rule as the Python front-end, so both write the same table.
    ## formatC pads "g" output to a fixed width, hence trimws().
    if (!is.null(digits)) return(trimws(formatC(v, format = "f", digits = digits)))
    if (v == round(v)) return(format(round(v), scientific = FALSE, trim = TRUE))
    trimws(formatC(v, format = "g", digits = 6))
}

.numbers_only <- function(values, helper) {
    if (!is.numeric(values) || !length(values) || anyNA(values)) {
        stop(helper, "() needs one or more numbers.", call. = FALSE)
    }
    values
}

numlist <- function(values, digits = NULL) {
    ## Numbers as a prose list, through siunitx: "250, 500 and 1000".
    values <- .numbers_only(values, "numlist")
    paste0("\\numlist{",
           paste(vapply(values, .plain_number, character(1), digits = digits), collapse = ";"),
           "}")
}

numset <- function(values, digits = NULL) {
    ## Numbers as a set, for math mode: $n \in \mthSimN$. siunitx's \numlist
    ## writes "250, 500 and 1000", which is right in prose and wrong in a set.
    values <- .numbers_only(values, "numset")
    paste0("\\{",
           paste0("\\num{", vapply(values, .plain_number, character(1), digits = digits), "}",
                  collapse = ", "),
           "\\}")
}

pkg_version <- function(name) {
    ## The version of an installed package, as this session sees it.
    latex_text(as.character(utils::packageVersion(name)))
}

## ---------------------------------------------------------------------------
## JSON, written by hand so this file needs no packages
## ---------------------------------------------------------------------------

.artefact_escape <- function(x) {
    x <- gsub("\\", "\\\\", x, fixed = TRUE)
    x <- gsub("\"", "\\\"", x, fixed = TRUE)
    gsub("\n", "\\n", x, fixed = TRUE)
}

.artefact_json_object <- function(named) {
    if (length(named) == 0L) return("{}")
    parts <- sprintf("\"%s\": \"%s\"",
                     .artefact_escape(names(named)),
                     .artefact_escape(unlist(named, use.names = FALSE)))
    paste0("{", paste(parts, collapse = ", "), "}")
}

.artefact_json_array <- function(values) {
    if (length(values) == 0L) return("[]")
    paste0("[", paste(sprintf("\"%s\"", .artefact_escape(values)), collapse = ", "), "]")
}

.artefact_to_json <- function(x) {
    ## General JSON for the extra fields a helper records, such as grid counts:
    ## named lists become objects, other lists and vectors become arrays.
    if (is.null(x)) return("null")
    if (is.list(x)) {
        nm <- names(x)
        if (!is.null(nm) && length(x) && all(nzchar(nm))) {
            parts <- vapply(seq_along(x), function(i) {
                paste0("\"", .artefact_escape(nm[i]), "\": ", .artefact_to_json(x[[i]]))
            }, character(1))
            return(paste0("{", paste(parts, collapse = ", "), "}"))
        }
        return(paste0("[", paste(vapply(x, .artefact_to_json, character(1)), collapse = ", "), "]"))
    }
    one <- function(v) {
        if (is.na(v)) return("null")
        if (is.character(v)) return(paste0("\"", .artefact_escape(v), "\""))
        if (is.logical(v)) return(if (v) "true" else "false")
        if (v == round(v) && abs(v) < 1e15) return(format(round(v), scientific = FALSE, trim = TRUE))
        format(v, digits = 15)
    }
    if (length(x) == 1L) return(one(x))
    paste0("[", paste(vapply(x, one, character(1)), collapse = ", "), "]")
}

.artefact_record <- function(path, macros = NULL, label = NULL, extra = NULL) {
    macro_file <- tempfile(fileext = ".json")
    reads_file <- tempfile(fileext = ".json")
    extra_file <- tempfile(fileext = ".json")
    on.exit(unlink(c(macro_file, reads_file, extra_file)), add = TRUE)

    writeLines(.artefact_json_object(macros), macro_file)
    writeLines(.artefact_json_array(ls(.artefact_reads)), reads_file)

    args <- c(file.path(.artefact_root, "tools", "record_provenance.py"),
              "--path", path,
              "--macros", macro_file,
              "--reads", reads_file)
    if (!is.null(extra)) {
        writeLines(.artefact_to_json(extra), extra_file)
        args <- c(args, "--extra", extra_file)
    }
    rule <- tryCatch(snakemake@rule, error = function(e) NULL)
    if (!is.null(rule)) args <- c(args, "--rule", rule)
    if (!is.null(label)) args <- c(args, "--label", label)

    status <- system2(.artefact_python(), shQuote(args), stdout = "", stderr = "")
    if (!identical(status, 0L)) {
        stop("Recording provenance for ", path, " failed. The artefact was written ",
             "but is not stamped, so the checks will reject it.", call. = FALSE)
    }
    invisible(path)
}

## ---------------------------------------------------------------------------
## Emitters
## ---------------------------------------------------------------------------

emit_numbers <- function(path, ...) {
    ## All the numbers from one computation belong in one file. The estimate,
    ## its standard error, its interval and its n come out of one fit and always
    ## go stale together, so they share a fate and should share a file.
    macros <- list(...)
    if (is.null(names(macros)) || any(names(macros) == "")) {
        stop("Every value passed to emit_numbers() needs a name, which becomes ",
             "the LaTeX macro name.", call. = FALSE)
    }
    .artefact_validate(path, macros)
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)

    names_sorted <- sort(names(macros))
    lines <- c(
        "% Generated. Do not edit; edit the code that produces it.",
        "% Rebuild with: make build",
        "",
        sprintf("\\artefactdefine{%s}{%s}", names_sorted,
                unlist(macros[names_sorted], use.names = FALSE))
    )
    writeLines(lines, path)
    .artefact_record(path, macros = macros[names_sorted])
    invisible(path)
}

save_figure <- function(path, plot = NULL, width = 6, height = 4, label = NULL, ...) {
    .artefact_validate(path)
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    if (is.null(plot)) {
        if (!requireNamespace("ggplot2", quietly = TRUE)) {
            stop("save_figure() needs either a plot object or ggplot2 installed.",
                 call. = FALSE)
        }
        plot <- ggplot2::last_plot()
    }
    if (inherits(plot, "ggplot")) {
        ggplot2::ggsave(path, plot = plot, width = width, height = height, ...)
    } else {
        grDevices::pdf(path, width = width, height = height, ...)
        on.exit(grDevices::dev.off(), add = TRUE)
        print(plot)
    }
    .artefact_record(path, label = label)
    invisible(path)
}

save_table <- function(path, x, label = NULL, ...) {
    ## A fragment for \input inside a table environment: no float wrapper and no
    ## caption. Those belong in the manuscript, where the caption can say what
    ## the table is for.
    if (!requireNamespace("knitr", quietly = TRUE)) {
        stop("save_table() needs knitr for kable().", call. = FALSE)
    }
    .artefact_validate(path)
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    body <- knitr::kable(x, format = "latex", booktabs = TRUE, ...)
    writeLines(c("% Generated. Do not edit; edit the code that produces it.",
                 as.character(body)), path)
    .artefact_record(path, label = label)
    invisible(path)
}

## ---------------------------------------------------------------------------
## Methods: learner grids
## ---------------------------------------------------------------------------

.artefact_bind <- function(frames) {
    ## Bind data frames by row, with NA where a frame lacks a column: a learner
    ## with no hyperparameters has none of the others' columns.
    cols <- unique(unlist(lapply(frames, names)))
    frames <- lapply(frames, function(d) {
        for (m in setdiff(cols, names(d))) d[[m]] <- NA
        d[cols]
    })
    do.call(rbind, frames)
}

.grid_cell <- function(vals, digits, max_listed) {
    if (is.numeric(vals)) {
        if (length(vals) == 1L) return(sprintf("\\num{%s}", .plain_number(vals, digits)))
        if (length(vals) <= max_listed) return(paste0("$", numset(vals, digits), "$"))
        return(sprintf("\\num{%d} values from \\num{%s} to \\num{%s}", length(vals),
                       .plain_number(vals[1L], digits),
                       .plain_number(vals[length(vals)], digits)))
    }
    shown <- latex_text(vals)
    if (length(shown) == 1L) return(shown)
    paste0("\\{", paste(shown, collapse = ", "), "\\}")
}

.edge_counts <- function(mine, p, exempt) {
    ## The edge rule for one tuned hyperparameter of one learner type, across
    ## fits: within each fit, does the configuration with the smallest cv_risk sit at
    ## the smallest or largest value of the grid?
    mine <- mine[!is.na(mine[[p]]) & is.finite(mine$cv_risk), , drop = FALSE]
    ## Rows without a fit form one group, as in the Python front-end.
    groups <- if ("fit" %in% names(mine)) {
        split(mine, ifelse(is.na(mine$fit), ".none", as.character(mine$fit)))
    } else {
        list(mine)
    }
    lower <- 0L; upper <- 0L; fits <- 0L; low <- Inf; high <- -Inf
    for (g in groups) {
        grid <- sort(unique(g[[p]]))
        ## With two values every choice is an edge, so the rule says nothing.
        if (length(grid) < 3L) next
        value <- g[[p]][which.min(g$cv_risk)]
        lo <- grid[1L]; hi <- grid[length(grid)]
        if (value == lo && !(lo %in% exempt)) lower <- lower + 1L
        if (value == hi && !(hi %in% exempt)) upper <- upper + 1L
        fits <- fits + 1L
        low <- min(low, lo); high <- max(high, hi)
    }
    if (fits == 0L) return(NULL)
    list(lower = lower, upper = upper, fits = fits, low = low, high = high)
}

grid_table <- function(path, rows, limits = list(), label = NULL, digits = NULL,
                       max_listed = 6) {
    ## A learner library's hyperparameters as a methods table, with the grids
    ## checked on the way. `rows` has one row per learner configuration and fit:
    ## `learner` (the learner type), one column per hyperparameter, `cv_risk`
    ## (that configuration's cross-validated risk in that fit), and optionally `fit`.
    ## A list of data frames is bound with NA for the columns a frame lacks.
    ##
    ## Within a learner type, a hyperparameter with one value is fixed and one
    ## with several is tuned. The table lists each with its value or its grid;
    ## a grid longer than `max_listed` is shown by its size and range. The grid
    ## check is the edge rule, and its counts go into the provenance record for
    ## `make methods`; a grid of two values is reported as such, because there
    ## every choice is an edge. `limits` names values that are hard limits of a
    ## parameter, such as list(max_depth = 1); an edge there is exempt.
    ##
    ## Name the path tables/methods-*.tex. The manuscript needs booktabs.
    df <- if (is.data.frame(rows)) rows else .artefact_bind(rows)
    if (!nrow(df) || !"learner" %in% names(df)) {
        stop("grid_table() needs rows with a 'learner'.", call. = FALSE)
    }
    ## cv_risk matters only for the grid check; a learner with no
    ## hyperparameters, such as a main-terms GLM, needs none.
    if (!"cv_risk" %in% names(df)) df$cv_risk <- NA_real_
    .artefact_validate(path)
    params <- setdiff(names(df), c("learner", "cv_risk", "fit"))
    learners <- unique(as.character(df$learner))
    lines <- c("% Generated. Do not edit; edit the code that produces it.",
               "\\begin{tabular}{llll}", "\\toprule",
               "Learner & Hyperparameter & Value or grid & Tuned \\\\", "\\midrule")
    edges <- list()
    for (ln in learners) {
        mine <- df[as.character(df$learner) == ln, , drop = FALSE]
        cells <- list()
        for (p in params) {
            v <- mine[[p]]
            v <- v[!is.na(v)]
            if (!length(v)) next
            vals <- if (is.numeric(v)) sort(unique(v)) else sort(unique(as.character(v)), method = "radix")
            tuned <- length(vals) > 1L
            cells[[length(cells) + 1L]] <- list(p = p, vals = vals, tuned = tuned)
            if (tuned && is.numeric(v)) {
                if (length(vals) == 2L) {
                    edges[[length(edges) + 1L]] <- list(learner = ln, param = p, two_values = TRUE)
                } else {
                    counts <- .edge_counts(mine, p, as.numeric(limits[[p]]))
                    if (!is.null(counts)) {
                        edges[[length(edges) + 1L]] <- c(list(learner = ln, param = p), counts)
                    }
                }
            }
        }
        if (!length(cells)) {
            lines <- c(lines, sprintf("%s & none & & \\\\", latex_text(ln)))
            next
        }
        for (i in seq_along(cells)) {
            cl <- cells[[i]]
            lines <- c(lines, sprintf("%s & %s & %s & %s \\\\",
                                      if (i == 1L) latex_text(ln) else "",
                                      latex_text(cl$p),
                                      .grid_cell(cl$vals, digits, max_listed),
                                      if (cl$tuned) "yes" else "no"))
        }
    }
    lines <- c(lines, "\\bottomrule", "\\end{tabular}")
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    writeLines(lines, path)
    .artefact_record(path, label = label, extra = list(edges = edges))
    invisible(path)
}
