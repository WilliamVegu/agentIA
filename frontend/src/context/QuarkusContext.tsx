import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  FactoryOrder,
  CreateOrderRequest,
  ClarificationAnswerItem,
  ArchitecturePattern,
  BuildTool,
  ArchitectureProposal,
  UserStory,
  DatabaseModelProposal,
  QuarkusExtensionItem,
  PublishQuarkusGitRequest,
  PublishQuarkusGitResponse
} from '../types/quarkusFactory';
import { quarkusFactoryService } from '../services/quarkusFactoryService';

interface QuarkusContextType {
  currentOrder: FactoryOrder | null;
  ordersList: FactoryOrder[];
  activeStep: number;
  setActiveStep: (step: number) => void;
  isLoading: boolean;
  error: string | null;
  refreshOrders: () => Promise<void>;
  selectOrder: (order: FactoryOrder) => void;
  resetCurrentOrder: () => void;
  createNewOrder: (req: CreateOrderRequest) => Promise<FactoryOrder>;
  submitAnswers: (answers: ClarificationAnswerItem[]) => Promise<void>;
  approveContract: (
    approvedBy: string,
    comments: string,
    modifiedOpenapi?: string,
    approveDatabaseModel?: boolean,
    modifiedUserStories?: UserStory[],
    modifiedDatabaseModel?: DatabaseModelProposal
  ) => Promise<void>;
  selectArchitecture: (pattern: ArchitecturePattern, buildTool: BuildTool, extensions?: QuarkusExtensionItem[]) => Promise<void>;
  generateArchetype: (pattern: ArchitecturePattern, buildTool: BuildTool, extensions?: QuarkusExtensionItem[]) => Promise<void>;
  suggestExtension: (query: string) => Promise<any>;
  generateSkeleton: () => Promise<void>;
  buildAndTest: () => Promise<void>;
  approveDelivery: (
    approvedBy: string,
    comments: string,
    repo: string,
    branch: string,
    gitToken?: string,
    commitMessage?: string
  ) => Promise<void>;
  publishToGit: (request: PublishQuarkusGitRequest) => Promise<PublishQuarkusGitResponse>;
}

const QuarkusContext = createContext<QuarkusContextType | undefined>(undefined);

export const QuarkusProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentOrder, setCurrentOrder] = useState<FactoryOrder | null>(null);
  const [ordersList, setOrdersList] = useState<FactoryOrder[]>([]);
  const [activeStep, setActiveStepState] = useState<number>(() => {
    const saved = localStorage.getItem('quarkus_active_step');
    return saved !== null ? parseInt(saved, 10) : 0;
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const setActiveStep = (step: number) => {
    setActiveStepState(step);
    localStorage.setItem('quarkus_active_step', String(step));
  };

  const resetCurrentOrder = () => {
    setCurrentOrder(null);
    localStorage.removeItem('quarkus_current_order_id');
    setActiveStep(0);
  };

  const refreshOrders = async () => {
    try {
      const orders = await quarkusFactoryService.listOrders();
      setOrdersList(orders);
      const savedOrderId = localStorage.getItem('quarkus_current_order_id');
      const orderIdToMatch = currentOrder?.id || savedOrderId;
      if (orderIdToMatch) {
        const found = orders.find(o => o.id === orderIdToMatch);
        if (found) {
          setCurrentOrder(found);
        }
      }
    } catch (err: any) {
      console.error('Error refreshing orders:', err);
    }
  };

  useEffect(() => {
    refreshOrders();
  }, []);

  const selectOrder = (order: FactoryOrder) => {
    setCurrentOrder(order);
    localStorage.setItem('quarkus_current_order_id', order.id);
    // Calcular automáticamente el paso sugerido según el estado
    if (order.status === 'Recibido' || order.status === 'Contrato en revisión') {
      setActiveStep(1); // Contrato OpenAPI & Revisión Dinámica
    } else if (order.status === 'Aprobado') {
      setActiveStep(2); // Arquitectura & Extensiones Quarkus
    } else if (order.status === 'Generando' || order.status === 'Probando') {
      setActiveStep(3); // Construcción & Pruebas
    } else if (order.status === 'En revisión') {
      setActiveStep(5); // Control 2: Revisión & Code Review
    } else if (order.status === 'Entregado') {
      setActiveStep(6); // Entrega DevOps & Descarga ZIP
    }
  };

  const createNewOrder = async (req: CreateOrderRequest): Promise<FactoryOrder> => {
    setIsLoading(true);
    setError(null);
    try {
      const created = await quarkusFactoryService.createOrder(req);
      setCurrentOrder(created);
      localStorage.setItem('quarkus_current_order_id', created.id);
      await refreshOrders();
      // Salto directo a la revisión del Contrato OpenAPI (sin cuestionario de preguntas)
      setActiveStep(1);
      return created;
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const submitAnswers = async (answers: ClarificationAnswerItem[]) => {
    if (!currentOrder) return;
    setIsLoading(true);
    setError(null);
    try {
      const updated = await quarkusFactoryService.submitAnswers(currentOrder.id, answers);
      setCurrentOrder(updated);
      await refreshOrders();
      setActiveStep(2); // Ir a Control 1 (Revisar y Congelar Contrato)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const approveContract = async (
    approvedBy: string,
    comments: string,
    modifiedOpenapi?: string,
    approveDatabaseModel: boolean = true,
    modifiedUserStories?: UserStory[],
    modifiedDatabaseModel?: DatabaseModelProposal
  ) => {
    if (!currentOrder) return;
    setIsLoading(true);
    setError(null);
    try {
      const updated = await quarkusFactoryService.approveContract(currentOrder.id, {
        approved_by: approvedBy,
        comments,
        modified_openapi: modifiedOpenapi || null,
        approve_database_model: approveDatabaseModel,
        modified_user_stories: modifiedUserStories,
        modified_database_model: modifiedDatabaseModel
      });
      setCurrentOrder(updated);
      await refreshOrders();
      setActiveStep(2); // Ir a Paso 3: Arquitectura y Extensiones Quarkus
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const selectArchitecture = async (pattern: ArchitecturePattern, buildTool: BuildTool, extensions?: QuarkusExtensionItem[]) => {
    if (!currentOrder) return;
    setIsLoading(true);
    setError(null);
    try {
      const activeExtList = extensions
        ? extensions.filter(e => e.is_selected).map(e => e.id.split(':').pop() || e.id)
        : (currentOrder.architecture_proposal?.recommended_extensions || []);

      const updated = await quarkusFactoryService.selectArchitecture(currentOrder.id, {
        selected_pattern: pattern,
        chosen_build_tool: buildTool,
        extensions: activeExtList,
        selected_extensions: extensions || currentOrder.architecture_proposal?.quarkus_extensions || []
      });
      setCurrentOrder(updated);
      await refreshOrders();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const generateArchetype = async (pattern: ArchitecturePattern, buildTool: BuildTool, extensions?: QuarkusExtensionItem[]) => {
    if (!currentOrder) return;
    setIsLoading(true);
    setError(null);
    try {
      const updated = await quarkusFactoryService.generateArchetype(currentOrder.id, {
        selected_pattern: pattern,
        chosen_build_tool: buildTool,
        extensions: extensions || currentOrder.quarkus_extensions || []
      });
      setCurrentOrder(updated);
      await refreshOrders();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const suggestExtension = async (query: string): Promise<any> => {
    if (!currentOrder) return null;
    return await quarkusFactoryService.suggestExtension(currentOrder.id, query);
  };

  const generateSkeleton = async () => {
    if (!currentOrder) return;
    setIsLoading(true);
    setError(null);
    try {
      const updated = await quarkusFactoryService.generateSkeleton(currentOrder.id);
      setCurrentOrder(updated);
      await refreshOrders();
      setActiveStep(3); // Mostrar tracking de construcción y QA
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const buildAndTest = async () => {
    if (!currentOrder) return;
    setIsLoading(true);
    setError(null);
    try {
      const updated = await quarkusFactoryService.buildAndTest(currentOrder.id);
      setCurrentOrder(updated);
      await refreshOrders();
      setActiveStep(5); // Ir a Control 2 (Revisión Final de Código, Pruebas y Code Review)
      setActiveStep(3); // Mantener en seguimiento para ver el 100% y el aviso de finalización
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const approveDelivery = async (
    approvedBy: string,
    comments: string,
    repo: string,
    branch: string,
    gitToken?: string,
    commitMessage?: string
  ) => {
    if (!currentOrder) return;
    setIsLoading(true);
    setError(null);
    try {
      const updated = await quarkusFactoryService.approveDelivery(currentOrder.id, {
        approved_by: approvedBy,
        comments,
        target_git_repo: repo,
        branch_name: branch,
        git_token: gitToken,
        commit_message: commitMessage
      });
      setCurrentOrder(updated);
      await refreshOrders();
      setActiveStep(6); // Ir a Entrega DevOps & Descarga ZIP
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const publishToGit = async (
    request: PublishQuarkusGitRequest
  ): Promise<PublishQuarkusGitResponse> => {
    if (!currentOrder) throw new Error("No hay un pedido activo seleccionado.");
    setIsLoading(true);
    setError(null);
    try {
      const res = await quarkusFactoryService.publishToGit(currentOrder.id, request);
      await refreshOrders();
      return res;
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <QuarkusContext.Provider
      value={{
        currentOrder,
        ordersList,
        activeStep,
        setActiveStep,
        isLoading,
        error,
        refreshOrders,
        selectOrder,
        resetCurrentOrder,
        createNewOrder,
        submitAnswers,
        approveContract,
        selectArchitecture,
        generateArchetype,
        suggestExtension,
        generateSkeleton,
        buildAndTest,
        approveDelivery,
        publishToGit
      }}
    >
      {children}
    </QuarkusContext.Provider>
  );
};

export const useQuarkus = () => {
  const context = useContext(QuarkusContext);
  if (!context) {
    throw new Error('useQuarkus debe ser usado dentro de un QuarkusProvider');
  }
  return context;
};

