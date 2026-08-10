<script setup lang="ts">
import { RouterView } from 'vue-router'
import DefaultLayout from './layouts/default-layout.vue'
import IconSprite from './components/aps/icon-sprite.vue'
</script>

<template>
  <IconSprite />
  <DefaultLayout>
    <RouterView />
  </DefaultLayout>
</template>
