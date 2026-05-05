// simplegallery — GalleryGrid, Lightbox, ExifPanel (no deps).
(function () {
  "use strict";
  if (typeof document === "undefined") return;

  var SWIPE_MIN = 50;

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
    } else {
      fn();
    }
  }

  // --- ExifPanel ----------------------------------------------------------

  function ExifPanel(root) {
    this.root = root;
    this.list = root.querySelector(".exif-list");
    this.empty = root.querySelector(".exif-empty");
  }

  ExifPanel.prototype.render = function (raw) {
    this.list.innerHTML = "";
    var data = parseExif(raw);
    var keys = data ? Object.keys(data) : [];
    if (!keys.length) {
      this.empty.hidden = false;
      return;
    }
    this.empty.hidden = true;
    var frag = document.createDocumentFragment();
    keys.forEach(function (key) {
      var dt = document.createElement("dt");
      dt.textContent = key;
      var dd = document.createElement("dd");
      dd.textContent = String(data[key]);
      frag.appendChild(dt);
      frag.appendChild(dd);
    });
    this.list.appendChild(frag);
  };

  ExifPanel.prototype.open = function () { this.root.dataset.open = "true"; };
  ExifPanel.prototype.close = function () { this.root.dataset.open = "false"; };
  ExifPanel.prototype.toggle = function () {
    if (this.root.dataset.open === "true") this.close();
    else this.open();
  };

  function parseExif(raw) {
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (e) { return null; }
  }

  // --- Lightbox -----------------------------------------------------------

  function Lightbox(items) {
    this.items = items;
    this.index = 0;
    this.previousFocus = null;
    this.touchStart = null;
    this.root = null;
    this.image = null;
    this.video = null;
    this.exif = null;
    this._historyPushed = false;
    this._suppressPopstate = false;
    this._build();
  }

  Lightbox.prototype._build = function () {
    var root = document.createElement("div");
    root.className = "lightbox";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", "Media viewer");
    root.hidden = true;
    root.innerHTML =
      '<div class="lightbox-stage">' +
        '<button type="button" class="lightbox-btn lightbox-close" aria-label="Close">×</button>' +
        '<button type="button" class="lightbox-btn lightbox-info" aria-label="Toggle EXIF">EXIF</button>' +
        '<a class="lightbox-btn lightbox-download" aria-label="Download original" download hidden>↓</a>' +
        '<button type="button" class="lightbox-btn lightbox-prev" aria-label="Previous">‹</button>' +
        '<button type="button" class="lightbox-btn lightbox-next" aria-label="Next">›</button>' +
        '<img class="lightbox-media lightbox-image" alt="" hidden>' +
        '<video class="lightbox-media lightbox-video" controls playsinline hidden></video>' +
        '<aside class="exif-panel" data-open="false">' +
          '<h2>EXIF</h2>' +
          '<dl class="exif-list"></dl>' +
          '<p class="exif-empty" hidden>No EXIF data.</p>' +
        '</aside>' +
      '</div>';
    document.body.appendChild(root);

    this.root = root;
    this.image = root.querySelector(".lightbox-image");
    this.video = root.querySelector(".lightbox-video");
    this.download = root.querySelector(".lightbox-download");
    this.exif = new ExifPanel(root.querySelector(".exif-panel"));

    var self = this;
    root.querySelector(".lightbox-close").addEventListener("click", function () { self.close(); });
    root.querySelector(".lightbox-prev").addEventListener("click", function () { self.prev(); });
    root.querySelector(".lightbox-next").addEventListener("click", function () { self.next(); });
    root.querySelector(".lightbox-info").addEventListener("click", function () { self.exif.toggle(); });

    root.addEventListener("click", function (ev) {
      if (ev.target === root || ev.target.classList.contains("lightbox-stage")) self.close();
    });

    document.addEventListener("keydown", function (ev) {
      if (root.hidden) return;
      if (ev.key === "Escape") { ev.preventDefault(); self.close(); }
      else if (ev.key === "ArrowLeft") { ev.preventDefault(); self.prev(); }
      else if (ev.key === "ArrowRight") { ev.preventDefault(); self.next(); }
      else if (ev.key === "Tab") self._trapFocus(ev);
    });

    root.addEventListener("touchstart", function (ev) {
      if (ev.touches.length !== 1) { self.touchStart = null; return; }
      self.touchStart = { x: ev.touches[0].clientX, y: ev.touches[0].clientY };
    }, { passive: true });

    root.addEventListener("touchend", function (ev) {
      var start = self.touchStart;
      self.touchStart = null;
      if (!start || !ev.changedTouches.length) return;
      var dx = ev.changedTouches[0].clientX - start.x;
      var dy = ev.changedTouches[0].clientY - start.y;
      if (Math.abs(dx) > SWIPE_MIN && Math.abs(dx) > Math.abs(dy)) {
        if (dx < 0) self.next(); else self.prev();
      }
    });
  };

  Lightbox.prototype.open = function (index, opts) {
    var fromHash = opts && opts.fromHash;
    var wasOpen = !this.root.hidden;
    if (!wasOpen) {
      this.previousFocus = document.activeElement;
      this.root.hidden = false;
      document.body.style.overflow = "hidden";
    }
    this.index = clamp(index, 0, this.items.length - 1);
    this._show(this.index);
    this._preloadNeighbors();
    if (!wasOpen) {
      var closeBtn = this.root.querySelector(".lightbox-close");
      if (closeBtn) closeBtn.focus();
    }
    this._syncHistory(wasOpen, fromHash);
  };

  Lightbox.prototype._syncHistory = function (wasOpen, fromHash) {
    var item = this.items[this.index];
    if (!item || !item.slug) return;
    var hash = "#m-" + item.slug;
    if (fromHash) {
      this._historyPushed = false;
      return;
    }
    if (!wasOpen) {
      if (location.hash !== hash) {
        history.pushState({ sg: true, slug: item.slug }, "", hash);
        this._historyPushed = true;
      } else {
        this._historyPushed = false;
      }
    } else {
      history.replaceState({ sg: true, slug: item.slug }, "", hash);
    }
  };

  Lightbox.prototype.close = function () {
    if (this.root.hidden) return;
    if (this._historyPushed) {
      this._historyPushed = false;
      history.back();
      return;
    }
    this._closeNow(true);
  };

  Lightbox.prototype._closeNow = function (clearHash) {
    var item = this.items[this.index];
    this.root.hidden = true;
    document.body.style.overflow = "";
    this._stopVideo();
    this.exif.close();
    if (clearHash && location.hash && /^#m-/.test(location.hash)) {
      this._suppressPopstate = true;
      history.replaceState(null, "", location.pathname + location.search);
      this._suppressPopstate = false;
    }
    if (item && item.slug) {
      var fig = document.getElementById("m-" + item.slug);
      if (fig && fig.scrollIntoView) {
        fig.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    }
    if (this.previousFocus && this.previousFocus.focus) {
      try { this.previousFocus.focus(); } catch (e) { /* ignore */ }
    }
    this.previousFocus = null;
  };

  Lightbox.prototype.prev = function () {
    if (!this.items.length) return;
    this.index = (this.index - 1 + this.items.length) % this.items.length;
    this._show(this.index);
    this._preloadNeighbors();
    this._syncHistory(true, false);
  };

  Lightbox.prototype.next = function () {
    if (!this.items.length) return;
    this.index = (this.index + 1) % this.items.length;
    this._show(this.index);
    this._preloadNeighbors();
    this._syncHistory(true, false);
  };

  Lightbox.prototype._findBySlug = function (slug) {
    if (!slug) return -1;
    for (var i = 0; i < this.items.length; i++) {
      if (this.items[i].slug === slug) return i;
    }
    return -1;
  };

  Lightbox.prototype._handlePopstate = function () {
    if (this._suppressPopstate) return;
    var slug = parseHashSlug(location.hash);
    var idx = this._findBySlug(slug);
    if (idx >= 0) {
      this._historyPushed = false;
      this.open(idx, { fromHash: true });
    } else if (!this.root.hidden) {
      this._historyPushed = false;
      this._closeNow(false);
    }
  };

  function parseHashSlug(hash) {
    if (!hash || hash.indexOf("#m-") !== 0) return "";
    return decodeURIComponent(hash.slice(3));
  }

  Lightbox.prototype._show = function (index) {
    var item = this.items[index];
    if (!item) return;
    this._stopVideo();
    if (item.kind === "video") {
      this.image.hidden = true;
      this.image.removeAttribute("src");
      this.video.hidden = false;
      this.video.poster = item.thumb || "";
      this.video.innerHTML = "";
      if (item.mp4) appendSource(this.video, item.mp4, "video/mp4");
      if (item.webm) appendSource(this.video, item.webm, "video/webm");
      this.video.load();
    } else {
      this.video.hidden = true;
      this.image.hidden = false;
      this.image.src = item.src || item.thumb || "";
      this.image.alt = item.name || "";
    }
    this._setDownload(item);
    this.exif.render(item.exif);
  };

  Lightbox.prototype._setDownload = function (item) {
    if (!this.download) return;
    var href = item.original || "";
    if (!href) {
      this.download.hidden = true;
      this.download.removeAttribute("href");
      this.download.removeAttribute("download");
      return;
    }
    this.download.hidden = false;
    this.download.href = href;
    var name = filenameFromPath(href) || item.name || "";
    if (name) this.download.setAttribute("download", name);
    else this.download.setAttribute("download", "");
  };

  function filenameFromPath(href) {
    if (!href) return "";
    var clean = href.split("?")[0].split("#")[0];
    var parts = clean.split("/");
    return decodeURIComponent(parts[parts.length - 1] || "");
  }

  Lightbox.prototype._preloadNeighbors = function () {
    var n = this.items.length;
    if (n < 2) return;
    var offsets = [-1, 1];
    for (var i = 0; i < offsets.length; i++) {
      var item = this.items[(this.index + offsets[i] + n) % n];
      if (item && item.kind !== "video" && item.src) {
        var img = new Image();
        img.src = item.src;
      }
    }
  };

  Lightbox.prototype._stopVideo = function () {
    try {
      this.video.pause();
      this.video.removeAttribute("src");
      this.video.innerHTML = "";
      this.video.load();
    } catch (e) { /* ignore */ }
  };

  Lightbox.prototype._trapFocus = function (ev) {
    var focusables = this.root.querySelectorAll(
      'button, [href], input, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) return;
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (ev.shiftKey && document.activeElement === first) {
      ev.preventDefault();
      last.focus();
    } else if (!ev.shiftKey && document.activeElement === last) {
      ev.preventDefault();
      first.focus();
    }
  };

  function appendSource(video, src, type) {
    var s = document.createElement("source");
    s.src = src;
    s.type = type;
    video.appendChild(s);
  }

  function clamp(n, lo, hi) {
    if (n < lo) return lo;
    if (n > hi) return hi;
    return n;
  }

  // --- GalleryGrid --------------------------------------------------------

  function GalleryGrid(root) {
    this.root = root;
    this.figures = Array.prototype.slice.call(root.querySelectorAll("figure"));
    this.items = this.figures.map(figureToItem);
    this.lightbox = new Lightbox(this.items);
    var self = this;
    function openFig(fig) {
      var slug = fig.dataset.slug || "";
      var idx = self.lightbox._findBySlug(slug);
      if (idx < 0) idx = self.figures.indexOf(fig);
      if (idx >= 0) self.lightbox.open(idx);
    }
    this.figures.forEach(function (fig) {
      var link = fig.querySelector("a.gallery-link");
      if (link) {
        link.addEventListener("click", function (ev) {
          if (ev.defaultPrevented) return;
          if (ev.button !== 0) return;
          if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
          ev.preventDefault();
          openFig(fig);
        });
      } else {
        fig.setAttribute("tabindex", "0");
        fig.setAttribute("role", "button");
        fig.addEventListener("click", function () { openFig(fig); });
        fig.addEventListener("keydown", function (ev) {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            openFig(fig);
          }
        });
      }
    });

    window.addEventListener("popstate", function () {
      self.lightbox._handlePopstate();
    });

    var initialSlug = parseHashSlug(location.hash);
    if (initialSlug) {
      var idx = this.lightbox._findBySlug(initialSlug);
      if (idx >= 0) this.lightbox.open(idx, { fromHash: true });
    }
  }

  GalleryGrid.prototype.refreshItems = function () {
    this.figures = Array.prototype.slice.call(this.root.querySelectorAll("figure"));
    this.items = this.figures.map(figureToItem);
    this.lightbox.items = this.items;
  };

  function figureToItem(fig) {
    return {
      kind: fig.dataset.kind || "image",
      name: (fig.querySelector("img") && fig.querySelector("img").alt) || "",
      slug: fig.dataset.slug || "",
      thumb: fig.dataset.thumb || (fig.querySelector("img") && fig.querySelector("img").src) || "",
      src: fig.dataset.src || "",
      original: fig.dataset.original || "",
      mp4: fig.dataset.mp4 || "",
      webm: fig.dataset.webm || "",
      exif: fig.dataset.exif || ""
    };
  }

  // --- GalleryControls (sort) --------------------------------------------

  function GalleryControls(scope, onChange) {
    this.scope = scope;
    this.onChange = onChange || null;
    this.root = scope.querySelector(".gallery-controls");
    if (!this.root) return;
    this.keySel = this.root.querySelector(".gc-key");
    this.orderSel = this.root.querySelector(".gc-order");
    this.targets = [];
    var sub = scope.querySelector(".subgallery-grid");
    var grid = scope.querySelector(".gallery-grid");
    if (sub) this.targets.push(sub);
    if (grid) this.targets.push(grid);
    var self = this;
    function apply() { self.sort(); }
    this.keySel.addEventListener("change", apply);
    this.orderSel.addEventListener("change", apply);
  }

  GalleryControls.prototype.sort = function () {
    if (!this.root) return;
    var key = this.keySel.value;
    var dir = this.orderSel.value === "desc" ? -1 : 1;
    for (var i = 0; i < this.targets.length; i++) {
      var container = this.targets[i];
      var children = Array.prototype.slice.call(container.children);
      children.sort(function (a, b) {
        var av, bv;
        if (key === "date") {
          av = parseFloat(a.dataset.mtime) || 0;
          bv = parseFloat(b.dataset.mtime) || 0;
          if (av === bv) return 0;
          return av < bv ? -1 * dir : 1 * dir;
        }
        av = (a.dataset.name || "").toLowerCase();
        bv = (b.dataset.name || "").toLowerCase();
        if (av === bv) return 0;
        return av < bv ? -1 * dir : 1 * dir;
      });
      var frag = document.createDocumentFragment();
      children.forEach(function (c) { frag.appendChild(c); });
      container.appendChild(frag);
    }
    if (this.onChange) this.onChange();
  };

  // --- bootstrap ----------------------------------------------------------

  ready(function () {
    document.documentElement.dataset.simplegallery = "ready";
    var mains = document.querySelectorAll("main");
    Array.prototype.forEach.call(mains, function (m) {
      var grid = m.querySelector(".gallery-grid[data-gallery]");
      var galleryGrid = grid ? new GalleryGrid(grid) : null;
      new GalleryControls(m, function () {
        if (galleryGrid) galleryGrid.refreshItems();
      });
    });
  });
})();
