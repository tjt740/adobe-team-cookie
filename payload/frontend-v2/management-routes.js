/* Register panel pages before the compiled application starts its first navigation. */
export const managementRoutes = [
  {path: 'external-members', name: 'external-members', component: {render: () => null},
    meta: {title: '外部子号', requiresAuth: true, okadPanel: 'extm-nav'}},
  {path: 'sub2', name: 'sub2', component: {render: () => null},
    meta: {title: 'Sub2 管理', requiresAuth: true, okadPanel: 'sub2-nav-mng'}}
];

export function legacyPanelRedirect(route) {
  if (route.path === '/login') return;
  const panel = managementRoutes.find(page => page.path === route.query.panel);
  if (!panel) return;
  const query = {...route.query};
  delete query.panel;
  return {path: '/' + panel.path, query, hash: route.hash, replace: true};
}
