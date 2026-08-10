import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import DocumentsView from '../views/DocumentsView.vue'
import EvaluationView from '../views/EvaluationView.vue'
import ExperimentsView from '../views/ExperimentsView.vue'

const routes = [
  { path: '/', name: 'chat', component: ChatView },
  { path: '/documents', name: 'documents', component: DocumentsView },
  { path: '/evaluation', name: 'evaluation', component: EvaluationView },
  { path: '/experiments', name: 'experiments', component: ExperimentsView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
