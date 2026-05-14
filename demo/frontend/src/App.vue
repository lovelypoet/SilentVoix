<template>
  <div class="dark" style="min-height: 100vh; background: #0b0f1a;">
    <header class="header">
      <div class="header-inner">
        <div class="logo">
          <span class="logo-icon">&#9856;</span>
          <span class="logo-text">SilentVoix</span>
        </div>
        <nav class="nav">
          <router-link to="/" class="nav-link" active-class="nav-link--active">Demo</router-link>
          <router-link to="/test" class="nav-link" active-class="nav-link--active">Test Lab</router-link>
        </nav>
      </div>
    </header>
    <main class="main">
      <router-view />
    </main>
    <div id="tts-highlight" class="tts-highlight"></div>
  </div>
</template>

<style>
.header {
  background: #141a2b;
  border-bottom: 1px solid #1e2740;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}
.logo-icon {
  font-size: 24px;
}
.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: #a5b4fc;
  letter-spacing: -0.3px;
}
.nav {
  display: flex;
  gap: 4px;
}
.nav-link {
  color: #94a3b8;
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s;
}
.nav-link:hover { color: #e2e8f0; background: #1e2740; }
.nav-link--active { color: #a5b4fc !important; background: #1e2740; }
.main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
.tts-highlight {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 50;
  pointer-events: none;
}
</style>
