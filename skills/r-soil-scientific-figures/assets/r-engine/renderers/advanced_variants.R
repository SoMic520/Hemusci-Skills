# Recipe-level rendering registry.
#
# Family modules register only variants whose scientific layout differs from the
# dependency-light baseline.  The core engine retains validation, typography,
# fonts, export and manifests.  Keeping these concerns separate makes visual
# variants testable without duplicating data-integrity code.

.recipe_override_registry <- new.env(parent = emptyenv())

register_recipe_override <- function(ids, renderer) {
  stopifnot(is.function(renderer), length(ids) > 0)
  for (id in ids) assign(id, renderer, envir = .recipe_override_registry)
  invisible(ids)
}

render_recipe_override <- function(dat, recipe_id, config) {
  if (!exists(recipe_id, envir = .recipe_override_registry, inherits = FALSE)) return(NULL)
  renderer <- get(recipe_id, envir = .recipe_override_registry, inherits = FALSE)
  renderer(dat, recipe_id, config)
}

.advanced_renderer_file <- if (exists(".advanced_renderer_path", inherits = TRUE) &&
                               nzchar(get(".advanced_renderer_path", inherits = TRUE))) {
  get(".advanced_renderer_path", inherits = TRUE)
} else {
  tryCatch(
    normalizePath(sys.frame(1)$ofile, winslash = "/", mustWork = TRUE),
    error = function(e) ""
  )
}
.advanced_renderer_root <- dirname(.advanced_renderer_file)
.advanced_family_modules <- c(
  "distribution_relationship.R",
  "interval_spatial.R",
  "network_hierarchy.R",
  "profile_image.R",
  "remaining_statistical.R",
  "remaining_domain.R"
)
for (.advanced_family_module in .advanced_family_modules) {
  .module_path <- file.path(.advanced_renderer_root, .advanced_family_module)
  if (file.exists(.module_path)) source(.module_path, encoding = "UTF-8")
}
