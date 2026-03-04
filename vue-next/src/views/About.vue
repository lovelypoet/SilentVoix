<script setup>
import { computed, ref } from 'vue'
import BaseCard from '../components/base/BaseCard.vue'

const teamPhotoUrl = `/pics/${encodeURIComponent('Ảnh nhóm V hand .webp')}`
const activeMemberId = ref(null)
const memberKey = (member) => member.id || member.name

const members = [
  {
    id: 'nguyen-duc-anh',
    name: 'Nguyễn Đức Anh (C)',
    role: 'AI Engineer',
    department: 'Information and Communication Technology (ICT)',
    category: 'Main Member',
    marker: { x: 46, y: 30 },
  },
  {
    id: 'do-hung-anh',
    name: 'Đỗ Hùng Anh',
    role: 'ML Ops Engineer',
    department: 'Information and Communication Technology (ICT)',
    category: 'Main Member',
    marker: { x: 63, y: 30 },
  },
  {
    id: 'do-tran-nam-anh',
    name: 'Đỗ Trần Nam Anh',
    role: 'Software Development and Operations Engineer',
    department: 'Information and Communication Technology (ICT)',
    category: 'Main Member',
    marker: { x: 15, y: 36 },
  },
  {
    id: 'le-huu-phuc-minh',
    name: 'Lê Hữu Phúc Minh',
    role: 'Hardware Engineer',
    department: 'Mechatronics (MET)',
    category: 'Main Member',
    marker: { x: 30, y: 33 },
  },
  {
    id: 'nguyen-duc-duong',
    name: 'Nguyễn Đức Dương',
    role: 'Hardware Engineer',
    department: 'Mechatronics (MET)',
    category: 'Main Member',
    marker: { x: 79, y: 35 },
  },
  {
    id: 'truong-viet-lam',
    name: 'Truong Viet Lam',
    role: 'Assistant',
    department: 'Mechatronics (MET)',
    category: 'Assistant',
    marker: { x: 23, y: 72 },
  },
  {
    name: 'Pham Gia Bao',
    role: 'Collaborator - Computer Vision',
    department: 'Information and Communication Technology (ICT)',
    category: 'Collaborator',
    marker: { x: 37, y: 72 },
  },
  {
    name: 'Luong Duc Anh',
    role: 'Collaborator - Machine Learning and Data Minning, Natural Language Processing',
    department: 'Information and Communication Technology (ICT)',
    category: 'Collaborator',
    marker: { x: 52, y: 72 },
  },
  {
    name: 'Do Nam Khanh',
    role: 'Collaborator - Natural Language Processing',
    department: 'Information and Communication Technology (ICT)',
    category: 'Collaborator',
    marker: { x: 66, y: 72 },
  },
  {
    name: 'Nguyen Xuan Duc',
    role: 'Collaborator - Computer Vision, Machine Learning and Data Minning',
    department: 'Information and Communication Technology (ICT)',
    category: 'Collaborator',
    marker: { x: 81, y: 72 },
  },
]

const mainMembers = computed(() => members.filter((member) => member.category === 'Main Member'))
const supportMembers = computed(() => members.filter((member) => member.category !== 'Main Member'))
</script>

<template>
  <div class="space-y-6">
    <div class="text-center mx-auto max-w-3xl">
      <h1 class="text-3xl font-bold text-white">About The Team</h1>
      <p class="text-sm text-slate-400 mt-1">The people behind SilentVoix and the model-monitoring platform.</p>
    </div>

    <BaseCard class="about-hero p-0 overflow-hidden">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-0">
        <div class="p-6 md:p-8 text-center lg:text-left">
          <p class="text-xs uppercase tracking-widest text-cyan-300/80">SilentVoix Team</p>
          <h2 class="text-2xl md:text-3xl font-bold text-white mt-2">Building Reliable AI + Hardware Systems</h2>
          <p class="text-sm md:text-base text-slate-300 mt-4">
            We combine software engineering, operations, and mechatronics to deliver robust sensor-driven AI experiences.
          </p>
          <p class="text-xs text-slate-400 mt-4">
            Hover a marker on the team photo to spotlight the corresponding member card.
          </p>
        </div>
        <div class="relative group">
          <img
            :src="teamPhotoUrl"
            alt="SilentVoix team"
            class="w-full h-64 lg:h-full object-cover"
            loading="lazy"
          />
          <button
            type="button"
            class="member-marker"
            :class="activeMemberId === 'nguyen-duc-anh' ? 'marker-active' : ''"
            :style="{ left: '15%', top: '36%' }"
            aria-label="Highlight Nguyễn Đức Anh (C)"
            @mouseenter="activeMemberId = 'nguyen-duc-anh'"
            @mouseleave="activeMemberId = null"
            @focus="activeMemberId = 'nguyen-duc-anh'"
            @blur="activeMemberId = null"
          >
            <span class="marker-pulse"></span>
          </button>

          <button
            type="button"
            class="member-marker"
            :class="activeMemberId === 'do-hung-anh' ? 'marker-active' : ''"
            :style="{ left: '30%', top: '33%' }"
            aria-label="Highlight Đỗ Hùng Anh"
            @mouseenter="activeMemberId = 'do-hung-anh'"
            @mouseleave="activeMemberId = null"
            @focus="activeMemberId = 'do-hung-anh'"
            @blur="activeMemberId = null"
          >
            <span class="marker-pulse"></span>
          </button>

          <button
            type="button"
            class="member-marker"
            :class="activeMemberId === 'do-tran-nam-anh' ? 'marker-active' : ''"
            :style="{ left: '46%', top: '30%' }"
            aria-label="Highlight Đỗ Trần Nam Anh"
            @mouseenter="activeMemberId = 'do-tran-nam-anh'"
            @mouseleave="activeMemberId = null"
            @focus="activeMemberId = 'do-tran-nam-anh'"
            @blur="activeMemberId = null"
          >
            <span class="marker-pulse"></span>
          </button>

          <button
            type="button"
            class="member-marker"
            :class="activeMemberId === 'le-huu-phuc-minh' ? 'marker-active' : ''"
            :style="{ left: '63%', top: '30%' }"
            aria-label="Highlight Lê Hữu Phúc Minh"
            @mouseenter="activeMemberId = 'le-huu-phuc-minh'"
            @mouseleave="activeMemberId = null"
            @focus="activeMemberId = 'le-huu-phuc-minh'"
            @blur="activeMemberId = null"
          >
            <span class="marker-pulse"></span>
          </button>

          <button
            type="button"
            class="member-marker"
            :class="activeMemberId === 'nguyen-duc-duong' ? 'marker-active' : ''"
            :style="{ left: '79%', top: '35%' }"
            aria-label="Highlight Nguyễn Đức Dương"
            @mouseenter="activeMemberId = 'nguyen-duc-duong'"
            @mouseleave="activeMemberId = null"
            @focus="activeMemberId = 'nguyen-duc-duong'"
            @blur="activeMemberId = null"
          >
            <span class="marker-pulse"></span>
          </button>
        </div>
      </div>
    </BaseCard>

    <div class="space-y-3">
      <h3 class="text-xl font-bold text-white text-center">Main Members</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <BaseCard
          v-for="member in mainMembers"
          :key="memberKey(member)"
          class="member-card transition-all duration-200"
          :class="{
            'member-card-active': activeMemberId === memberKey(member),
            'member-card-dim': activeMemberId && activeMemberId !== memberKey(member)
          }"
          @mouseenter="activeMemberId = memberKey(member)"
          @mouseleave="activeMemberId = null"
        >
          <div class="text-xs uppercase tracking-wider text-cyan-300/80">Main Member</div>
          <h3 class="text-xl font-bold text-white mt-2">{{ member.name }}</h3>
          <p class="text-slate-200 mt-2">{{ member.role }}</p>
          <p class="text-sm text-slate-400 mt-1">{{ member.department }}</p>
        </BaseCard>
      </div>
    </div>

    <div class="space-y-3">
      <h3 class="text-xl font-bold text-white text-center">Support Team</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <BaseCard
          v-for="member in supportMembers"
          :key="memberKey(member)"
          class="member-card transition-all duration-200"
          :class="{
            'member-card-active': activeMemberId === memberKey(member),
            'member-card-dim': activeMemberId && activeMemberId !== memberKey(member)
          }"
          @mouseenter="activeMemberId = memberKey(member)"
          @mouseleave="activeMemberId = null"
        >
          <div class="text-xs uppercase tracking-wider text-cyan-300/80">{{ member.category }}</div>
          <h3 class="text-xl font-bold text-white mt-2">{{ member.name }}</h3>
          <p class="text-slate-200 mt-2">{{ member.role }}</p>
          <p class="text-sm text-slate-400 mt-1">{{ member.department }}</p>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<style scoped>
.about-hero {
  border: 1px solid rgba(103, 232, 249, 0.2);
  background: linear-gradient(130deg, rgba(15, 23, 42, 0.95), rgba(15, 23, 42, 0.7));
}

.member-card {
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(15, 23, 42, 0.45));
}

.member-card-active {
  transform: scale(1.03);
  border-color: rgba(45, 212, 191, 0.7);
  box-shadow: 0 12px 22px -14px rgba(45, 212, 191, 0.55);
}

.member-card-dim {
  transform: scale(0.97);
  opacity: 0.72;
}

.member-marker {
  position: absolute;
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 9999px;
  border: 2px solid rgba(12, 74, 110, 0.9);
  background: rgba(45, 212, 191, 0.95);
  transform: translate(-50%, -50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.85);
  transition: transform 180ms ease, background-color 180ms ease;
}

.member-marker:hover,
.member-marker:focus-visible,
.marker-active {
  transform: translate(-50%, -50%) scale(1.2);
  background: rgba(103, 232, 249, 1);
}

.marker-pulse {
  position: absolute;
  inset: -7px;
  border-radius: 9999px;
  border: 1px solid rgba(103, 232, 249, 0.45);
  opacity: 0.8;
  animation: marker-ping 1.8s infinite;
}

@keyframes marker-ping {
  0% {
    transform: scale(0.7);
    opacity: 0.8;
  }
  70% {
    transform: scale(1.15);
    opacity: 0;
  }
  100% {
    transform: scale(1.2);
    opacity: 0;
  }
}

@media (max-width: 768px) {
  .member-card-active,
  .member-card-dim {
    transform: none;
    opacity: 1;
  }
}
</style>
