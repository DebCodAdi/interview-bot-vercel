import {fireEvent,render,screen} from '@testing-library/react';
import {expect,test,vi} from 'vitest';
vi.mock('@vapi-ai/web',()=>({default:vi.fn()}));
vi.mock('@monaco-editor/react',()=>({default:({value,onChange})=><textarea aria-label="Monaco editor" value={value} onChange={event=>onChange(event.target.value)}/> }));
import App,{INTERVIEW_SECONDS,TOTAL_SECONDS,mergeEvaluationReports} from './App';
import CodingScreen from './components/CodingScreen';
import EvaluationScreen from './components/EvaluationScreen';
import Transcript from './components/Transcript';

test('uses a fixed three minute interview and twenty minute coding window',()=>{
  expect(INTERVIEW_SECONDS).toBe(180);
  expect(TOTAL_SECONDS).toBe(1380);
  render(<App/>);
  expect(screen.getByText(/3 minute interview/i)).toBeInTheDocument();
  expect(screen.getByText(/20 minute coding challenge/i)).toBeInTheDocument();
  expect(screen.getByRole('button',{name:/launch interview/i})).toBeDisabled();
});

test('coding screen renders Monaco, question, language and hidden-test actions',()=>{
  render(<CodingScreen profile={{candidate_name:'Candidate'}} role="Software Engineer" time="20:00" question={{problem:'Return two indices.',examples:[{input:'nums=[2,7], target=9',output:'[0,1]'}]}} language="python" setLanguage={()=>{}} code="def solution(nums, target): pass" onCode={()=>{}} onCheckpoint={()=>{}} onRun={()=>{}} onSubmit={()=>{}} onFinish={()=>{}} result={null} messages={[]}/>);
  expect(screen.getByLabelText('Monaco editor')).toBeInTheDocument();
  expect(screen.getByText('Return two indices.')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:/run tests/i})).toBeInTheDocument();
});

test('transcript and evaluation are separate reusable views',()=>{
  const {rerender}=render(<Transcript messages={[{role:'candidate',content:'I use a hash map.'}]}/>);
  expect(screen.getByText(/I use a hash map/)).toBeInTheDocument();
  rerender(<EvaluationScreen report={{overall_score:80,technical_score:82,coding_score:90,communication_score:70,summary:'Evidence based.',evidence:['Linear time approach.']}} onReset={()=>{}}/>);
  expect(screen.getByText('80/100')).toBeInTheDocument();
  expect(screen.getByText('Linear time approach.')).toBeInTheDocument();
});

test('new interview action delegates to the full session reset',()=>{
  const onReset=vi.fn();
  render(<EvaluationScreen report={null} onReset={onReset}/>);
  fireEvent.click(screen.getByRole('button',{name:/new interview/i}));
  expect(onReset).toHaveBeenCalledOnce();
});

test('combines cached technical and coding evaluations with configured weights',()=>{
  const report=mergeEvaluationReports({technical_score:80,communication_score:70,evidence:['Technical evidence.']},{coding_score:90,communication_score:90,evidence:['Coding evidence.']});
  expect(report).toMatchObject({technical_score:80,coding_score:90,communication_score:80,overall_score:84});
  expect(report.evidence).toEqual(['Technical evidence.','Coding evidence.']);
});
