<script setup>
import BaseCard from '../components/base/BaseCard.vue'

const teamPhotoUrl = `/pics/${encodeURIComponent('Ảnh nhóm V hand .webp')}`

const mainMembers = [
  {
    name: 'Nguyễn Đức Anh',
    role: 'Team Lead',
    department: 'Information and Communication Technology (ICT)',
  },
  {
    name: 'Đỗ Hùng Anh',
    role: 'Software Engineer',
    department: 'Information and Communication Technology (ICT)',
  },
  {
    name: 'Đỗ Trần Nam Anh',
    role: 'Software Development and Operations Engineer',
    department: 'Information and Communication Technology (ICT)',
  },
  {
    name: 'Lê Hữu Phúc Minh',
    role: 'Hardware Engineer',
    department: 'Mechatronics (MET)',
  },
  {
    name: 'Nguyễn Đức Dương',
    role: 'Hardware Engineer',
    department: 'Mechatronics (MET)',
  },
]

const assistants = [
  { name: 'Truong Viet Lam' },
]

const collaborators = [
  { name: 'Pham Gia Bao' },
  { name: 'Luong Duc Anh' },
  { name: 'Do Nam Khanh' },
  { name: 'Nguyen Xuan Duc' },
]
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
        </div>
        <img
          :src="teamPhotoUrl"
          alt="SilentVoix team"
          class="w-full h-64 lg:h-full object-cover"
          loading="lazy"
        />
      </div>
    </BaseCard>

    <div class="space-y-3">
      <h3 class="text-xl font-bold text-white">Main Members</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <BaseCard
          v-for="member in mainMembers"
          :key="member.name"
          class="member-card"
        >
          <div class="text-xs uppercase tracking-wider text-cyan-300/80">Main Member</div>
          <h3 class="text-xl font-bold text-white mt-2">{{ member.name }}</h3>
          <p class="text-slate-200 mt-2">{{ member.role }}</p>
          <p class="text-sm text-slate-400 mt-1">{{ member.department }}</p>
        </BaseCard>
      </div>
    </div>

    <div class="space-y-3">
      <h3 class="text-xl font-bold text-white">Support Team</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <BaseCard class="member-card">
          <div class="text-xs uppercase tracking-wider text-cyan-300/80">Assistant</div>
          <p v-for="person in assistants" :key="person.name" class="text-slate-200 mt-2">{{ person.name }}</p>
        </BaseCard>

        <BaseCard class="member-card">
          <div class="text-xs uppercase tracking-wider text-cyan-300/80">Collaborators</div>
          <p v-for="person in collaborators" :key="person.name" class="text-slate-200 mt-2">{{ person.name }}</p>
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
</style>
