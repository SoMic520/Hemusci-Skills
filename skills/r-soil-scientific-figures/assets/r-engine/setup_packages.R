#!/usr/bin/env Rscript

# Cross-platform package setup. Installation is kept separate from plotting.

options(repos = c(CRAN = "https://cloud.r-project.org"))
required <- c(
  "ggplot2", "ggtext", "jsonlite", "openxlsx", "ragg", "readxl", "scales",
  "systemfonts", "sysfonts", "showtext", "svglite"
)
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  message("Installing missing packages: ", paste(missing, collapse = ", "))
  install.packages(missing, dependencies = NA)
}
remaining <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(remaining)) stop("Packages still missing: ", paste(remaining, collapse = ", "))
message("R environment ready on ", R.version.string, " / ", R.version$platform)
